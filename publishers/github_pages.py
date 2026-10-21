import os
from typing import Any

import httpx


def publish_github_pr(content: dict[str, Any], preview_hash: str) -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_PAGES_REPO")
    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN and GITHUB_PAGES_REPO must be configured.")

    path = os.environ.get("GITHUB_PAGES_PATH", "proofpoint/approved.md")
    branch = f"proofpoint/{preview_hash[:12]}"
    markdown = _render_markdown(content, preview_hash)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    with httpx.Client(timeout=30.0, headers=headers) as client:
        repo_info = client.get(f"https://api.github.com/repos/{repo}")
        repo_info.raise_for_status()
        default_branch = repo_info.json()["default_branch"]

        ref = client.get(f"https://api.github.com/repos/{repo}/git/ref/heads/{default_branch}")
        ref.raise_for_status()
        sha = ref.json()["object"]["sha"]

        created = client.post(
            f"https://api.github.com/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha},
        )
        if created.status_code not in (201, 422):
            created.raise_for_status()

        existing = client.get(f"https://api.github.com/repos/{repo}/contents/{path}", params={"ref": branch})
        put_body: dict[str, Any] = {
            "message": "Add approved Proofpoint project copy",
            "content": _b64(markdown),
            "branch": branch,
        }
        if existing.status_code == 200:
            put_body["sha"] = existing.json()["sha"]
        elif existing.status_code != 404:
            existing.raise_for_status()

        written = client.put(f"https://api.github.com/repos/{repo}/contents/{path}", json=put_body)
        written.raise_for_status()

        pull = client.post(
            f"https://api.github.com/repos/{repo}/pulls",
            json={
                "title": "Publish approved Proofpoint copy",
                "head": branch,
                "base": default_branch,
                "body": (
                    "Approved career copy from Proofpoint.\n\n"
                    f"Preview hash: `{preview_hash}`\n"
                ),
            },
        )
        if pull.status_code == 422:
            pulls = client.get(
                f"https://api.github.com/repos/{repo}/pulls",
                params={"head": f"{repo.split('/')[0]}:{branch}", "state": "open"},
            )
            pulls.raise_for_status()
            items = pulls.json()
            if items:
                return {"status": "exists", "url": items[0]["html_url"], "branch": branch}
        pull.raise_for_status()
        return {"status": "opened", "url": pull.json()["html_url"], "branch": branch}


def _render_markdown(content: dict[str, Any], preview_hash: str) -> str:
    website = content.get("personal_website_url") or ""
    bullets = content.get("selected_website_bullets") or content.get("selected_github_bullets") or []
    lines = [
        "# Approved project copy",
        "",
        content.get("github_summary") or content.get("website_copy") or "",
        "",
    ]
    if website:
        lines.extend([f"Site: {website}", ""])
    if content.get("website_copy"):
        lines.extend(["## Website copy", "", content["website_copy"], ""])
    if bullets:
        lines.append("## Highlights")
        lines.extend(f"- {item['text']}" for item in bullets)
        lines.append("")
    lines.extend(["", f"Preview hash: `{preview_hash}`", ""])
    return "\n".join(lines)


def _b64(text: str) -> str:
    import base64
    return base64.b64encode(text.encode("utf-8")).decode("ascii")
