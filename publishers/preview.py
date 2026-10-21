import hashlib
import json
import os
from typing import Any


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def publisher_status() -> dict[str, bool]:
    return {
        "overleaf": bool(os.environ.get("OVERLEAF_GIT_URL")),
        "github": bool(os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_PAGES_REPO")),
        "linkedin": bool(os.environ.get("LINKEDIN_ACCESS_TOKEN") and os.environ.get("LINKEDIN_PERSON_URN")),
    }
