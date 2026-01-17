from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db import connection


@dataclass(frozen=True)
class LocalGroupInfo:
    group_id: str
    is_leader: bool
    source_table: str


_REQUIRED_COLUMNS = {"email", "group_id", "is_leader"}
_CACHE_KEY_TABLE = "local_roster:table"
_CACHE_TTL_SECONDS = 60 * 60


_SAFE_TABLE_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _safe_table_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = str(value).strip().strip('"')
    if not v:
        return None
    return v if _SAFE_TABLE_RE.match(v) else None


def _detect_roster_table() -> Optional[str]:
    """Best-effort detection of the Supabase roster table.

    We look for a public table containing columns: email, group_id, is_leader.
    """
    vendor = connection.vendor

    try:
        with connection.cursor() as cursor:
            if vendor == "postgresql":
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND column_name IN ('email', 'group_id', 'is_leader')
                    GROUP BY table_name
                    HAVING COUNT(DISTINCT column_name) = 3
                    ORDER BY
                      CASE WHEN table_name = 'students' THEN 0 ELSE 1 END,
                      table_name
                    LIMIT 1;
                    """
                )
                row = cursor.fetchone()
                return row[0] if row else None

            # SQLite/dev fallback: use Django introspection + PRAGMA.
            tables = [t.name for t in connection.introspection.get_table_list(cursor)]
            for t in tables:
                try:
                    cursor.execute(f'PRAGMA table_info("{t}")')
                    cols = {r[1] for r in cursor.fetchall()}
                    if _REQUIRED_COLUMNS.issubset(cols):
                        return t
                except Exception:
                    continue
    except Exception:
        return None

    return None


def get_roster_table_name() -> Optional[str]:
    # Allow explicit override to avoid mis-detection.
    override = _safe_table_name(getattr(settings, 'GROUP_ROSTER_TABLE', None))
    if override:
        return override

    cached = cache.get(_CACHE_KEY_TABLE)
    if isinstance(cached, str) and cached:
        return cached

    table = _detect_roster_table()
    if table:
        cache.set(_CACHE_KEY_TABLE, table, _CACHE_TTL_SECONDS)
    return table


def _has_column(table: str, column: str) -> bool:
    try:
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                cursor.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = %s
                    LIMIT 1;
                    """,
                    [table, column],
                )
                return cursor.fetchone() is not None

            cursor.execute(f'PRAGMA table_info("{table}")')
            cols = {r[1] for r in cursor.fetchall()}
            return column in cols
    except Exception:
        return False


def get_local_group_info(email: str, *, roll_number: Optional[str] = None) -> Optional[LocalGroupInfo]:
    """Lookup student's group_id and leader flag from Supabase roster table.

    Supports lookup by:
    - email (case-insensitive)
    - roll_number token inside roll_number column (pipe-separated list)
    """
    email_norm = (email or "").strip().lower()
    roll = (roll_number or '').strip()

    if not email_norm and not roll:
        return None

    table = get_roster_table_name()
    if not table:
        return None

    has_roll = bool(roll) and _has_column(table, 'roll_number')

    try:
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                if has_roll:
                    cursor.execute(
                        f"""
                        SELECT group_id, is_leader
                        FROM public.\"{table}\"
                        WHERE (LOWER(email) = %s)
                           OR (%s = ANY(regexp_split_to_array(roll_number, '\\|')))
                        LIMIT 1;
                        """,
                        [email_norm, roll],
                    )
                else:
                    cursor.execute(
                        f'SELECT group_id, is_leader FROM public."{table}" WHERE LOWER(email) = %s LIMIT 1;',
                        [email_norm],
                    )
            else:
                # SQLite fallback: best-effort by email only.
                cursor.execute(
                    f'SELECT group_id, is_leader FROM "{table}" WHERE LOWER(email) = ? LIMIT 1;',
                    [email_norm],
                )

            row = cursor.fetchone()
            if not row:
                return None

            group_id_raw, is_leader_raw = row[0], row[1]
            if group_id_raw is None:
                return None

            group_id = str(group_id_raw).strip()
            if not group_id:
                return None

            is_leader = bool(is_leader_raw)
            return LocalGroupInfo(group_id=group_id, is_leader=is_leader, source_table=table)
    except Exception:
        return None


def get_local_group_info_for_user(user) -> Optional[LocalGroupInfo]:
    """Convenience wrapper to lookup by email and/or user's external id."""
    roll_candidate = getattr(user, 'pbl_user_id', None)
    return get_local_group_info(getattr(user, 'email', ''), roll_number=roll_candidate)
