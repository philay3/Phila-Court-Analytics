"""Thin database access for the pipeline (Task 21.3).

psycopg 3 (sync). This module owns connection construction and NOTHING else: no
connection pooling, no ORM, no query helpers, no schema knowledge. The
``DATABASE_URL`` is read at the CLI boundary (``cli.py``) and passed in here —
this module never reads the environment and never auto-loads ``.env`` (a load
must be explicit; the same posture the salt precedent set for the parser).

A missing or empty connection string is a hard failure with a clear message
(salt precedent): callers surface it as a nonzero exit, and this guard makes an
empty URL unrepresentable even if a caller forgets to check.
"""

from __future__ import annotations

import psycopg


def connect(database_url: str) -> psycopg.Connection:
    """Open a psycopg 3 connection from an explicit connection string.

    Raises ``ValueError`` on a missing/empty URL rather than letting psycopg
    emit an opaque error. Autocommit is left at psycopg's default (off): the
    loader manages one transaction per docket explicitly.
    """
    if not database_url or not database_url.strip():
        raise ValueError(
            "DATABASE_URL is required and must be non-empty "
            "(its value is never printed or logged)"
        )
    return psycopg.connect(database_url)
