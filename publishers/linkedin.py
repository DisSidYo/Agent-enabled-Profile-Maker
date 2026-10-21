import os
from typing import Any

import httpx


def publish_linkedin_post(content: dict[str, Any]) -> dict[str, str]:
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    person = os.environ.get("LINKEDIN_PERSON_URN")
    if not token or not person:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN must be configured.")

    text = (content.get("linkedin_post") or "").strip()
    if not text:
        raise RuntimeError("No LinkedIn post was selected in the approved preview.")

    author = person if person.startswith("urn:") else f"urn:li:person:{person}"
    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post("https://api.linkedin.com/v2/ugcPosts", json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"LinkedIn API rejected the post ({response.status_code}).")
        post_id = response.headers.get("x-restli-id") or response.json().get("id", "")
        return {"status": "published", "id": post_id}
