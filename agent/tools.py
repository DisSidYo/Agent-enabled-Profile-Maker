"""
Tools the agent is allowed to call.

Two things live here for each tool:
  1. a JSON schema (in TOOLS) describing it to the LLM — name, description,
     what arguments it takes. This is what gets sent in the API call so the
     model knows what's available.
  2. the actual Python function that runs when the model asks for that tool.

TOOL_FUNCTIONS maps schema name -> real function, so the agent loop can look
up "which code do I run" purely from the name the model returned.
"""

import subprocess

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_changed_files",
            "description": "List which files changed between two git refs in the repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {"type": "string", "description": "base ref, e.g. HEAD~1"},
                    "head": {"type": "string", "description": "head ref, e.g. HEAD"},
                },
                "required": ["base", "head"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_git_diff",
            "description": "Read the actual code diff between two git refs in the repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {"type": "string", "description": "base ref, e.g. HEAD~1"},
                    "head": {"type": "string", "description": "head ref, e.g. HEAD"},
                },
                "required": ["base", "head"],
            },
        },
    },
]


def list_changed_files(base: str, head: str, repo_path: str = ".") -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", "--name-only", f"{base}..{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "(no files changed)"


def read_git_diff(base: str, head: str, repo_path: str = ".") -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", f"{base}..{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    # cap length so one giant diff can't blow out the context window
    return (result.stdout or "(no diff found)")[:8000]


TOOL_FUNCTIONS = {
    "list_changed_files": list_changed_files,
    "read_git_diff": read_git_diff,
}
