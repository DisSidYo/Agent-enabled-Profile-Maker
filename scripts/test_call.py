"""
Step 0 sanity check.

This makes exactly one LLM call, routed through the local LiteLLM
gateway, and prints the response. It proves nothing more than:
  - the gateway is up and can reach a real model
  - auth (LITELLM_MASTER_KEY) works
  - the call gets logged as a trace in Langfuse

No agent logic, no tools, no loop. That comes after this works.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.environ["LITELLM_MASTER_KEY"],
    base_url="http://localhost:4000/v1",  # <- the gateway, not the model provider
)

response = client.chat.completions.create(
    model="primary",  # matches model_name in litellm/config.yaml
    messages=[
        {"role": "user", "content": "Reply with exactly: harness step 0 works."}
    ],
    metadata={
        # tags like this are what let you filter traces in Langfuse later
        "trace_name": "step0_sanity_check",
    },
)

print(response.choices[0].message.content)
print("\nIf you see the reply above, the gateway works.")
print("Now check your Langfuse project dashboard — a trace named")
print("'step0_sanity_check' should appear within a few seconds.")
