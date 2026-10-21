import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from pydantic import BaseModel, Field
from starlette.responses import Response

from agent.jsonutil import parse_model_json
from agent.loop import run_agent
from agent.tools import gather_evidence
from agent.verifier import verify_claims
from publishers import (
    canonical_hash,
    publisher_status,
    publish_github_pr,
    publish_linkedin_post,
    publish_overleaf,
)

load_dotenv()

app = FastAPI(title="Proofpoint", version="0.1.0")
PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIST = PROJECT_ROOT / "web" / "dist"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
CLIENT_HEADER = "proofpoint-web"
ROLES = [
    {"id": "Software Development", "short": "Development"},
    {"id": "AI / ML", "short": "AI / ML"},
    {"id": "Data Analytics", "short": "Analytics"},
    {"id": "Consulting", "short": "Consulting"},
]
ALLOWED_ROLES = {role["id"] for role in ROLES}


class RepoRequest(BaseModel):
    repo_path: str = Field(min_length=1, max_length=1000)


class GenerateRequest(RepoRequest):
    prompt: str = Field(min_length=10, max_length=3000)
    roles: list[str] = Field(min_length=1, max_length=4)
    base: str = Field(default="ROOT", min_length=1, max_length=200)
    head: str = Field(default="HEAD", min_length=1, max_length=200)


class ResumeBullet(BaseModel):
    role: str
    text: str = Field(min_length=1, max_length=1200)


class ApprovedContent(BaseModel):
    repo: dict[str, str]
    selected_resume_bullets: list[ResumeBullet] = Field(default_factory=list)
    selected_github_bullets: list[ResumeBullet] = Field(default_factory=list)
    selected_website_bullets: list[ResumeBullet] = Field(default_factory=list)
    selected_linkedin_bullets: list[ResumeBullet] = Field(default_factory=list)
    github_summary: str = ""
    website_copy: str = ""
    personal_website_url: str = ""
    linkedin_summary: str = ""
    linkedin_post: str = ""


class PublishRequest(BaseModel):
    preview_hash: str = Field(min_length=64, max_length=64)
    content: ApprovedContent


def _git(repo_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _assert_workspace(path: Path) -> None:
    roots_raw = os.environ.get("PROOFPOINT_REPO_ROOTS", str(Path.home()))
    roots = [Path(item).expanduser().resolve() for item in roots_raw.split(os.pathsep) if item.strip()]
    resolved = path.resolve()
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise HTTPException(status_code=400, detail="That folder is outside the allowed workspace.")


def _repo_details(repo_path: str) -> dict[str, str]:
    path = Path(repo_path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Choose an existing local repository folder.")
    _assert_workspace(path)

    root = _git(str(path), "rev-parse", "--show-toplevel")
    if root.returncode:
        raise HTTPException(status_code=400, detail="That folder is not inside a Git repository.")

    root_path = Path(root.stdout.strip()).resolve()
    _assert_workspace(root_path)
    branch = _git(str(root_path), "branch", "--show-current")
    status = _git(str(root_path), "status", "--short")
    first = _git(str(root_path), "rev-list", "--max-parents=0", "HEAD")
    if branch.returncode or status.returncode:
        raise HTTPException(status_code=400, detail="Git could not read this repository.")
    first_commit = first.stdout.strip().splitlines()[-1] if first.stdout.strip() else ""
    return {
        "path": str(root_path),
        "branch": branch.stdout.strip() or "(detached HEAD)",
        "working_tree": status.stdout.strip() or "clean",
        "first_commit": first_commit,
        "suggested_base": "ROOT",
    }


def _validate_ref(repo_path: str, ref: str) -> str:
    if ref in {"ROOT", EMPTY_TREE}:
        return EMPTY_TREE
    if ref.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_./@{}^~+-]+", ref):
        raise HTTPException(status_code=400, detail=f"Invalid Git ref: {ref}")
    result = _git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if result.returncode:
        raise HTTPException(status_code=400, detail=f"Git ref '{ref}' was not found.")
    return result.stdout.strip()


def _parse_model_result(result: dict[str, Any], roles: list[str]) -> dict[str, Any]:
    content = result.get("result")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=502, detail=result.get("error", "The model returned no content."))

    try:
        data = parse_model_json(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="The model returned invalid JSON; please try again.") from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="The model response must be a JSON object.")

    bullets = data.get("resume_bullets")
    if not isinstance(bullets, list):
        raise HTTPException(status_code=502, detail="The model response is missing resume bullets.")

    clean_bullets = []
    bullet_counts: dict[str, int] = {}
    for item in bullets:
        if not isinstance(item, dict):
            continue
        role, text = item.get("role"), item.get("text")
        if (
            role in roles
            and bullet_counts.get(role, 0) < 4
            and isinstance(text, str)
            and text.strip()
        ):
            clean_bullets.append({"role": role, "text": text.strip()[:1200]})
            bullet_counts[role] = bullet_counts.get(role, 0) + 1

    def clean_text(field: str, limit: int) -> str:
        value = data.get(field, "")
        if not isinstance(value, str):
            raise HTTPException(status_code=502, detail=f"The model returned an invalid '{field}' field.")
        return value.strip()[:limit]

    checklist = data.get("checklist")
    evidence_notes = data.get("evidence_notes")
    if not isinstance(checklist, list) or not isinstance(evidence_notes, list):
        raise HTTPException(status_code=502, detail="The model response is missing review details.")
    clean_checklist = [
        item.strip()[:300] for item in checklist if isinstance(item, str) and item.strip()
    ][:6]
    if not clean_checklist:
        raise HTTPException(status_code=502, detail="The model returned no review checklist.")
    return {
        "resume_bullets": clean_bullets,
        "github_summary": clean_text("github_summary", 2000),
        "website_copy": clean_text("website_copy", 2000),
        "linkedin_summary": clean_text("linkedin_summary", 2000),
        "linkedin_post": clean_text("linkedin_post", 3000),
        "checklist": clean_checklist,
        "evidence_notes": [
            x.strip()[:500] for x in evidence_notes if isinstance(x, str) and x.strip()
        ][:6],
    }


def _assert_preview(request: PublishRequest) -> dict[str, Any]:
    payload = request.content.model_dump()
    if canonical_hash(payload) != request.preview_hash:
        raise HTTPException(
            status_code=409,
            detail="Content no longer matches the approved preview. Re-approve before publishing.",
        )
    return payload


@app.middleware("http")
async def protect_local_api(request: Request, call_next) -> Response:
    if request.url.path.startswith("/api/"):
        host = request.headers.get("host", "").split(":")[0].strip("[]").lower()
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "This API only accepts local requests."}, status_code=403)
        if request.url.path != "/api/health" and request.headers.get("x-proofpoint-client") != CLIENT_HEADER:
            return JSONResponse({"detail": "Missing local client header."}, status_code=403)
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/roles")
def list_roles() -> dict[str, list[dict[str, str]]]:
    return {"roles": ROLES}


@app.get("/api/publishers")
def list_publishers() -> dict[str, bool]:
    return publisher_status()


@app.post("/api/repo")
def inspect_repo(request: RepoRequest) -> dict[str, str]:
    return _repo_details(request.repo_path)


@app.post("/api/generate")
def generate(request: GenerateRequest) -> dict[str, Any]:
    unknown_roles = set(request.roles) - ALLOWED_ROLES
    if unknown_roles:
        raise HTTPException(status_code=400, detail="One or more requested resume profiles are not supported.")

    repo = _repo_details(request.repo_path)
    base_sha = _validate_ref(repo["path"], request.base)
    head_sha = _validate_ref(repo["path"], request.head)
    if base_sha == head_sha:
        raise HTTPException(status_code=400, detail="Choose two different commits to compare.")

    range_label = "the full project (empty tree to HEAD)" if base_sha == EMPTY_TREE else (
        f"Git refs '{request.base}' and '{request.head}'"
    )
    task = (
        f"Analyze {range_label} "
        f"(resolved {base_sha[:12]} and {head_sha[:12]}). "
        f"Generate distinct content for these resume profiles: {', '.join(request.roles)}.\n\n"
        f"User's direction: {request.prompt.strip()}\n\n"
        "Inspect README, manifests, the file tree, changed files, and the diff using the provided "
        "read-only tools. Do not modify the repository, call external services, or claim that anything was published."
    )
    try:
        result = run_agent(
            task,
            repo_path=repo["path"],
            base_ref=base_sha,
            head_ref=head_sha,
        )
        evidence = gather_evidence(repo["path"], base_sha, head_sha)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=504, detail="Git took too long to inspect this repository.") from error
    except OpenAIError as error:
        raise HTTPException(
            status_code=502,
            detail=f"LiteLLM generation failed: {error}",
        ) from error

    parsed = _parse_model_result(result, request.roles)
    texts = [
        *(item["text"] for item in parsed["resume_bullets"]),
        parsed["github_summary"],
        parsed["website_copy"],
        parsed["linkedin_summary"],
        parsed["linkedin_post"],
    ]
    return {
        **parsed,
        "verification": verify_claims(texts, evidence),
        "repo": repo,
        "base": request.base,
        "head": request.head,
    }


@app.post("/api/approve")
def approve(content: ApprovedContent) -> dict[str, Any]:
    payload = content.model_dump()
    return {"preview_hash": canonical_hash(payload), "content": payload}


@app.post("/api/publish/overleaf")
def publish_to_overleaf(request: PublishRequest) -> dict[str, str]:
    payload = _assert_preview(request)
    try:
        return publish_overleaf(payload)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/publish/github")
def publish_to_github(request: PublishRequest) -> dict[str, str]:
    payload = _assert_preview(request)
    try:
        return publish_github_pr(payload, request.preview_hash)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"GitHub publish failed: {error}") from error


@app.post("/api/publish/linkedin")
def publish_to_linkedin(request: PublishRequest) -> dict[str, str]:
    payload = _assert_preview(request)
    try:
        return publish_linkedin_post(payload)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        return FileResponse(WEB_DIST / "index.html")
