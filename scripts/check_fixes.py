from agent.jsonutil import parse_model_json
from agent.redact import redact_secrets
from agent.verifier import verify_claims
from publishers.preview import canonical_hash

fenced = """```json
{"a": 1}
```"""
assert parse_model_json(fenced) == {"a": 1}

redacted = redact_secrets("token sk-abcdefghijklmnop and ghp_abcdefghijklmnopqrstuv")
assert "[REDACTED]" in redacted
assert "sk-" not in redacted

flags = verify_claims(["Shipped Kubernetes and served 10000 users"], "python flask app")
kinds = {item["kind"] for item in flags}
assert "technology" in kinds
assert "number" in kinds

assert canonical_hash({"b": 1, "a": 2}) == canonical_hash({"a": 2, "b": 1})
print("ok")
