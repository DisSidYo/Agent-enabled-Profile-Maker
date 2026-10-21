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

from pathlib import Path
import subprocess

from .limits import TOOL_RESULT_LIMIT
from .redact import redact_secrets

SENSITIVE_PATHSPECS = [
    ":!.env",
    ":!.env.*",
    ":!**/.env",
    ":!**/.env.*",
    ":!*credentials*",
    ":!**/*credentials*",
    ":!.npmrc",
    ":!**/.npmrc",
    ":!.pypirc",
    ":!**/.pypirc",
    ":!**/id_rsa",
    ":!**/id_dsa",
    ":!**/id_ecdsa",
    ":!**/id_ed25519",
    ":!*.pem",
    ":!**/*.pem",
    ":!*.key",
    ":!**/*.key",
    ":!*.tfstate",
    ":!**/*.tfstate",
    ":!*.tfstate.*",
    ":!**/*.tfstate.*",
    ":!**/.aws/credentials",
    ":!**/kubeconfig",
    ":!**/*.p12",
    ":!**/*.pfx",
]

MANIFEST_NAMES = (
    "README.md",
    "README.rst",
    "README",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "Gemfile",
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_changed_files",
            "description": "List which files changed between two git refs in the repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {"type": "string", "description": "base ref, e.g. ROOT or HEAD~1"},
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
                    "base": {"type": "string", "description": "base ref, e.g. ROOT or HEAD~1"},
                    "head": {"type": "string", "description": "head ref, e.g. HEAD"},
                },
                "required": ["base", "head"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_repo_context",
            "description": "Read README, dependency manifests, and a file tree so bullets can describe the whole project, not only one commit.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _git(repo_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def _cap(text: str, limit: int = TOOL_RESULT_LIMIT) -> str:
    redacted = redact_secrets(text)
    if len(redacted) <= limit:
        return redacted
    notice = f"\n[truncated at {limit} characters; the model did not see the rest]"
    keep = limit - len(notice)
    return redacted[:keep] + notice


def list_changed_files(base: str, head: str, repo_path: str = ".") -> str:
    result = _git(
        repo_path, "diff", "--name-only", base, head, "--", ".", *SENSITIVE_PATHSPECS,
    )
    if result.returncode:
        raise RuntimeError(f"Could not list changed files: {result.stderr.strip()}")
    return _cap(result.stdout.strip() or "(no files changed)")


def read_git_diff(base: str, head: str, repo_path: str = ".") -> str:
    result = _git(repo_path, "diff", base, head, "--", ".", *SENSITIVE_PATHSPECS)
    if result.returncode:
        raise RuntimeError(f"Could not read Git diff: {result.stderr.strip()}")
    return _cap(result.stdout or "(no diff found)")


def read_repo_context(repo_path: str = ".", **_kwargs) -> str:
    root = Path(repo_path)
    chunks: list[str] = []

    tree = _git(str(root), "ls-files")
    if tree.returncode == 0:
        files = [line for line in tree.stdout.splitlines() if line.strip()][:250]
        chunks.append("FILE TREE:\n" + "\n".join(files))

    for name in MANIFEST_NAMES:
        path = root / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"{name}:\n{text[:2500]}")

    return _cap("\n\n".join(chunks) or "(no repository context found)")


def gather_evidence(repo_path: str, base: str, head: str) -> str:
    parts = [
        read_repo_context(repo_path=repo_path),
        list_changed_files(base, head, repo_path=repo_path),
        read_git_diff(base, head, repo_path=repo_path),
    ]
    return redact_secrets("\n\n".join(parts))


TOOL_FUNCTIONS = {
    "list_changed_files": list_changed_files,
    "read_git_diff": read_git_diff,
    "read_repo_context": read_repo_context,
}
