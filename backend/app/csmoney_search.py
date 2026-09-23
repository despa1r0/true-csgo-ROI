"""Short-lived, deduplicated storefront searches without catalogue writes."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .database import get_connection


RESULT_TTL_SECONDS = 1800
MAX_QUERY_LENGTH = 100


def expire_searches(connection: Any) -> None:
    """Discard expired payloads while retaining short-lived expired IDs."""
    connection.execute(
        "UPDATE csmoney_text_search_jobs SET active = FALSE, result = NULL, error = NULL "
        "WHERE active AND expires_at <= NOW()"
    )
    connection.execute(
        "DELETE FROM csmoney_text_search_jobs "
        "WHERE NOT active AND expires_at < NOW() - INTERVAL '1 day'"
    )


def normalize_query(value: str) -> tuple[str, str]:
    query = " ".join(unicodedata.normalize("NFKC", value).split())
    if (len(query) < 2 or len(query) > MAX_QUERY_LENGTH
            or any(unicodedata.category(character)[0] == "C" for character in query)
            or not re.search(r"\w", query, re.UNICODE)):
        raise ValueError("Search query must contain 2–100 printable characters and a letter or digit")
    return query, query.casefold()


def enqueue_search(value: str) -> dict[str, Any]:
    query, normalized = normalize_query(value)
    with get_connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (normalized,))
        expire_searches(connection)
        row = connection.execute(
            """
            INSERT INTO csmoney_text_search_jobs
                (request_id, normalized_query, query, status, expires_at)
            VALUES (%s, %s, %s, 'queued', NOW() + (%s * INTERVAL '1 second'))
            ON CONFLICT (normalized_query) WHERE active DO NOTHING
            RETURNING request_id, status
            """,
            (uuid4(), normalized, query, RESULT_TTL_SECONDS),
        ).fetchone()
        if row is None:
            row = connection.execute(
                "SELECT request_id, status FROM csmoney_text_search_jobs "
                "WHERE normalized_query = %s AND active",
                (normalized,),
            ).fetchone()
    return dict(row)


def get_search(request_id: UUID) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT request_id, query, status, created_at, finished_at, expires_at,
                   error, result
            FROM csmoney_text_search_jobs WHERE request_id = %s
            """,
            (request_id,),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    from datetime import datetime, timezone
    if result["expires_at"] <= datetime.now(timezone.utc):
        result.update(status="expired", result=None, error=None)
    return result


def claim_search(*, lease_seconds: int = 180) -> dict[str, Any] | None:
    with get_connection() as connection:
        expire_searches(connection)
        row = connection.execute(
            """
            WITH candidate AS (
                SELECT request_id FROM csmoney_text_search_jobs
                WHERE expires_at > NOW() AND
                    (status = 'queued' OR (status = 'running' AND lease_until <= NOW()))
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE csmoney_text_search_jobs j
            SET status = 'running', lease_until = NOW() + (%s * INTERVAL '1 second')
            FROM candidate c WHERE j.request_id = c.request_id
            RETURNING j.request_id, j.query
            """,
            (lease_seconds,),
        ).fetchone()
    return dict(row) if row else None


def finish_search(request_id: UUID, status: str, *, result: dict | None = None,
                  error: str | None = None) -> None:
    if status not in {"complete", "empty", "blocked", "error"}:
        raise ValueError("Invalid terminal search status")
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE csmoney_text_search_jobs SET status = %s, finished_at = NOW(),
                expires_at = NOW() + (%s * INTERVAL '1 second'),
                lease_until = NULL, result = %s, error = %s
            WHERE request_id = %s AND status = 'running' AND expires_at > NOW()
            """,
            (status, RESULT_TTL_SECONDS, Jsonb(result) if result is not None else None,
             error[:500] if error else None, request_id),
        )
