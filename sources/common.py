"""Shared filtering + normalization helpers for the remote-jobs ingestors.

Kept deliberately small and dependency-light. BeautifulSoup is used only to
flatten the HTML descriptions that RemoteOK / WWR ship into the list-of-
paragraphs shape that JobAd.details expects (matching what the kariera
scraper already produces from JSON-LD)."""

from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup


# Keep aligned with the spec. Lowercased; we match on substring against the
# ad's tags AND title to keep recall high (RemoteOK tags are inconsistent).
TECH_TAGS: frozenset[str] = frozenset(
    {
        "python", "java", "javascript", "typescript", "golang", "go",
        "rust", "scala", "kotlin", "ruby", "php", "c#", "c++",
        "react", "angular", "vue", "node", "django", "flask", "fastapi",
        "spring",
        "postgres", "mysql", "mongodb", "redis", "kafka", "airflow",
        "spark", "hadoop", "dbt", "snowflake", "bigquery",
        "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
        "devops", "sre", "backend", "frontend", "fullstack",
        "data engineer", "ml engineer", "mlops",
        "site reliability", "platform engineer",
        "api", "microservice", "qa automation", "test automation",
    }
)


# Substrings (lowercased) that mark a posting as US-only. Patterns like
# "Worldwide", "Europe", "EMEA", "Anywhere" are explicitly allowed by leaving
# them out of this list.
US_ONLY_PATTERNS: tuple[str, ...] = (
    "us only",
    "usa only",
    "united states only",
    "north america only",
)


_EXPERIENCE_RE = re.compile(
    r"\b(principal|staff|lead|senior|sr\.?|junior|jr\.?|intern)\b",
    re.IGNORECASE,
)
_EXPERIENCE_MAP = {
    "principal": "Principal",
    "staff": "Staff",
    "lead": "Lead",
    "senior": "Senior",
    "sr": "Senior",
    "sr.": "Senior",
    "junior": "Junior",
    "jr": "Junior",
    "jr.": "Junior",
    "intern": "Intern",
}


_SINGLE_WORD_TAGS = frozenset(t for t in TECH_TAGS if " " not in t and not any(c in t for c in "#+"))
_MULTI_OR_SYMBOL_TAGS = tuple(t for t in TECH_TAGS if t not in _SINGLE_WORD_TAGS)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def has_tech_tag(title: str, tags: Iterable[str]) -> bool:
    """True if any TECH_TAGS entry matches the title or any provided tag.

    Single-word tags match on token equality (so 'go' won't fire on 'growth'
    and 'api' won't fire on 'therapist'). Multi-word and symbol tags ('data
    engineer', 'c#', 'c++') match on substring, which is safe because they
    have no common false-positive overlaps."""
    haystack_str = (title + " " + " ".join(tags)).lower()
    tokens = set(_TOKEN_RE.findall(haystack_str))
    if tokens & _SINGLE_WORD_TAGS:
        return True
    return any(tag in haystack_str for tag in _MULTI_OR_SYMBOL_TAGS)


def is_us_only(location: str | None) -> bool:
    if not location:
        return False
    loc = location.lower()
    return any(pat in loc for pat in US_ONLY_PATTERNS)


def infer_min_experience(title: str) -> str:
    m = _EXPERIENCE_RE.search(title or "")
    if not m:
        return "N/A"
    return _EXPERIENCE_MAP.get(m.group(1).lower(), "N/A")


def html_to_details(html: str | None) -> list[str]:
    """Flatten an HTML blob into a list of non-empty stripped paragraphs."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"])
    if blocks:
        out = [b.get_text(" ", strip=True) for b in blocks]
    else:
        # Fall back to newline-split when the description is plain text or
        # uses <br> tags without paragraph wrappers.
        text = soup.get_text("\n", strip=True)
        out = [ln.strip() for ln in text.splitlines()]
    return [s for s in out if s]


def normalize_tags(tags: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if not t:
            continue
        norm = t.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out
