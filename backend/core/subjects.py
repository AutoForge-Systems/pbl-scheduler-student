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
}


def normalize_subject(value: str) -> str:
    return (value or "").strip()


def is_allowed_subject(value: str) -> bool:
    return normalize_subject(value) in ALLOWED_SUBJECTS
