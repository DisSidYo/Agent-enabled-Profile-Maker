import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MARKER_START = "% PROOFPOINT:START"
MARKER_END = "% PROOFPOINT:END"


def publish_overleaf(content: dict[str, Any]) -> dict[str, str]:
    remote = os.environ.get("OVERLEAF_GIT_URL")
    if not remote:
        raise RuntimeError("OVERLEAF_GIT_URL is not configured.")

    relative = os.environ.get("OVERLEAF_RESUME_FILE", "proofpoint-approved.tex")
    bullets = content.get("selected_resume_bullets") or []
    body = "\n".join(f"\\item {item['text']}" for item in bullets) or "\\item (no resume bullets selected)"
    block = f"{MARKER_START}\n\\begin{{itemize}}\n{body}\n\\end{{itemize}}\n{MARKER_END}\n"

    with tempfile.TemporaryDirectory(prefix="proofpoint-overleaf-") as tmp:
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", remote, tmp],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if clone.returncode:
            raise RuntimeError("Could not clone the Overleaf Git remote.")

        target = Path(tmp) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if MARKER_START in existing and MARKER_END in existing:
                before, rest = existing.split(MARKER_START, 1)
                _, after = rest.split(MARKER_END, 1)
                target.write_text(before + block + after.lstrip("\n"), encoding="utf-8")
            else:
                target.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")
        else:
            target.write_text(block, encoding="utf-8")

        subprocess.run(["git", "-C", tmp, "add", relative], check=True, timeout=10)
        committed = subprocess.run(
            [
                "git", "-C", tmp,
                "-c", "user.email=proofpoint@local",
                "-c", "user.name=Proofpoint",
                "commit", "-m", "Update approved Proofpoint resume bullets",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if committed.returncode:
            if "nothing to commit" in (committed.stdout + committed.stderr).lower():
                return {"status": "unchanged", "file": relative}
            raise RuntimeError("Overleaf commit failed.")

        pushed = subprocess.run(
            ["git", "-C", tmp, "push", "origin", "HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if pushed.returncode:
            raise RuntimeError("Overleaf git push failed.")
        return {"status": "published", "file": relative}
