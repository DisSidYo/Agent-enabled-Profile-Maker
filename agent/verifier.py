import re
from typing import Iterable

TECH_TERMS = [
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn", "huggingface",
    "langchain", "llama", "openai", "anthropic", "numpy", "pandas", "polars",
    "spark", "hadoop", "airflow", "dbt", "snowflake", "bigquery", "redshift",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "kafka", "rabbitmq", "graphql", "grpc", "protobuf",
    "react", "next.js", "nextjs", "vue", "angular", "svelte", "django", "flask",
    "fastapi", "express", "spring", "rails", "laravel", "dotnet", ".net",
    "kubernetes", "k8s", "docker", "terraform", "ansible", "aws", "gcp", "azure",
    "lambda", "s3", "ec2", "cloudflare", "vercel", "netlify",
    "typescript", "javascript", "python", "golang", "rust", "java", "kotlin",
    "swift", "c++", "c#", "ruby", "php", "scala",
    "pytorch lightning", "xgboost", "lightgbm", "catboost",
]

_TECH_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in sorted(TECH_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\b")


def _evidence_blob(evidence: str) -> str:
    return (evidence or "").lower()


def verify_claims(texts: Iterable[str], evidence: str) -> list[dict[str, str]]:
    blob = _evidence_blob(evidence)
    flags: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for text in texts:
        if not isinstance(text, str) or not text.strip():
            continue
        lower = text.lower()
        for match in _TECH_RE.finditer(text):
            term = match.group(0)
            key = ("tech", term.lower(), text)
            if term.lower() not in blob and key not in seen:
                seen.add(key)
                flags.append({
                    "kind": "technology",
                    "claim": term,
                    "text": text,
                    "reason": f"'{term}' does not appear in the repository evidence.",
                })
        for match in _NUMBER_RE.finditer(text):
            raw = match.group(0)
            if _skip_number(raw, lower):
                continue
            key = ("num", raw, text)
            if raw.lower() not in blob and raw.replace(",", "") not in blob and key not in seen:
                seen.add(key)
                flags.append({
                    "kind": "number",
                    "claim": raw,
                    "text": text,
                    "reason": f"Number '{raw}' does not appear in the repository evidence.",
                })
    return flags


def _skip_number(raw: str, surrounding: str) -> bool:
    digits = raw.replace(",", "").replace("%", "")
    try:
        value = float(digits)
    except ValueError:
        return True
    if raw.endswith("%"):
        return False
    if 1990 <= value <= 2035 and "." not in raw:
        return True
    if value <= 5 and "," not in raw:
        return True
    return False
