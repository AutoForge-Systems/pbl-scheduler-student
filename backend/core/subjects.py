"""Subject constants and helpers.

Temporary business rules:
- Only two subjects exist.
- Each faculty evaluates exactly one subject.

This module intentionally avoids DB schema changes.
"""

from __future__ import annotations

ALLOWED_SUBJECTS = {
    "Web Development",
    "Compiler Design",
    "DAA",
    "JAVA",
    "Deep Learning",
}


_SUBJECT_ALIASES = {
    # PBL variants -> canonical subjects used inside scheduler
    "full stack web development": "Web Development",
    "fullstack web development": "Web Development",
    "fswd": "Web Development",
    "web dev": "Web Development",
    "webdevelopment": "Web Development",
    "compilerdesign": "Compiler Design",
    "cd": "Compiler Design",
}


def _norm_key(value: str) -> str:
    # Lowercase, collapse whitespace.
    return " ".join((value or "").strip().split()).lower()


def normalize_subject(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    key = _norm_key(raw)

    # Canonical match (case-insensitive)
    for subj in ALLOWED_SUBJECTS:
        if _norm_key(subj) == key:
            return subj

    # Alias match
    mapped = _SUBJECT_ALIASES.get(key)
    if mapped:
        return mapped

    return raw


def is_allowed_subject(value: str) -> bool:
    return normalize_subject(value) in ALLOWED_SUBJECTS
