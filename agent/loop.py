"""
The ReAct-style loop. This is the whole "agent":

  1. Send the conversation so far (system prompt + task + any tool results
     already gathered) to the model, along with the list of tools it's
     allowed to use.
  2. The model either:
       a) asks to call a tool (message.tool_calls is non-empty) — we run
          the real Python function, append the result to the conversation
          as a "tool" message, and go back to step 1.
       b) gives a final answer (message.tool_calls is empty) — we stop and
          return it.
  3. MAX_STEPS exists so a confused model can't loop forever burning tokens.

Every call goes through the LiteLLM gateway (base_url=localhost:4000), so
every step of this loop shows up as a span in Langfuse automatically —
that's the whole point of routing through the gateway instead of calling
OpenAI directly.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .jsonutil import parse_model_json
from .limits import TOOL_RESULT_LIMIT
from .prompts import SYSTEM_PROMPT
from .tools import TOOL_FUNCTIONS, TOOLS

load_dotenv()

MAX_STEPS = 8


def _client() -> OpenAI:
    api_key = os.environ.get("LITELLM_MASTER_KEY")
    if not api_key:
        raise RuntimeError("LITELLM_MASTER_KEY is not configured.")
    return OpenAI(
        api_key=api_key,
        base_url="http://localhost:4000/v1",
    )


def _looks_like_json(content: str | None) -> bool:
    if not isinstance(content, str) or not content.strip():
        return False
    try:
        parse_model_json(content)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _finalize_json(client: OpenAI, messages: list) -> str | None:
    payload = {
        "model": "primary",
        "messages": messages + [{
            "role": "user",
            "content": "Return only the final JSON object with the required keys. No markdown.",
        }],
        "metadata": {"trace_name": "resume_bullet_agent_json"},
    }
    try:
        response = client.chat.completions.create(
            **payload,
            response_format={"type": "json_object"},
        )
    except Exception:
        response = client.chat.completions.create(**payload)
    return response.choices[0].message.content


def run_agent(
    task: str,
    repo_path: str = ".",
    base_ref: str = "",
    head_ref: str = "",
) -> dict:
    client = _client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model="primary",
            messages=messages,
            tools=TOOLS,
            metadata={"trace_name": "resume_bullet_agent"},
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            if _looks_like_json(message.content):
                return {"result": message.content, "steps_taken": step + 1}
            finalized = _finalize_json(client, messages)
            return {"result": finalized, "steps_taken": step + 1}

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                fn_args = {}
            if not isinstance(fn_args, dict):
                fn_args = {}
            fn_args["repo_path"] = repo_path
            if base_ref:
                fn_args["base"] = base_ref
            if head_ref:
                fn_args["head"] = head_ref

            print(f"[step {step}] tool call: {fn_name}({fn_args})")
            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn is None:
                result = f"Unknown tool: {fn_name}"
            else:
                result = fn(**fn_args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)[:TOOL_RESULT_LIMIT],
                }
            )

    finalized = _finalize_json(client, messages)
    if finalized:
        return {"result": finalized, "steps_taken": MAX_STEPS}
    return {"result": None, "error": f"hit MAX_STEPS={MAX_STEPS} without a final answer"}


if __name__ == "__main__":
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else "ROOT"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

    task = (
        f"Analyze the changes between git refs '{base}' and '{head}' in this "
        f"repository and produce resume bullet points, per your instructions."
    )

    output = run_agent(task)
    print("\n--- final output ---")
    print(json.dumps(output, indent=2))
