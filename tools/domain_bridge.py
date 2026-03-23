from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Sequence


INFRA_DB_PATH = Path(__file__).resolve().parent.parent / "script3.db"


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or INFRA_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_polling_db(db_path: Path | str | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spamhaus_infra_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                source TEXT NOT NULL DEFAULT 'spamhaus',
                source_job_id TEXT,
                note TEXT NOT NULL DEFAULT '',
                queued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                consumed_at TIMESTAMP
            )
            """
        )
        conn.commit()


def normalize_domains(domains: Iterable[str]) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for item in domains:
        domain = str(item or "").strip().lower()
        if domain and domain not in seen:
            seen.add(domain)
            normalized.append(domain)
    return normalized


def enqueue_spamhaus_domains(
    domains: Sequence[str],
    *,
    source_job_id: str = "",
    note: str = "",
    db_path: Path | str | None = None,
) -> dict:
    normalized = normalize_domains(domains)
    if not normalized:
        raise ValueError("No valid domains were provided for infrastructure polling.")

    init_polling_db(db_path)
    inserted = 0
    reactivated = 0

    with _connect(db_path) as conn:
        for domain in normalized:
            existing = conn.execute(
                """
                SELECT id, status
                FROM spamhaus_infra_queue
                WHERE domain = ?
                """,
                (domain,),
            ).fetchone()
            if existing:
                if existing["status"] != "pending":
                    conn.execute(
                        """
                        UPDATE spamhaus_infra_queue
                        SET status = 'pending',
                            source = 'spamhaus',
                            source_job_id = ?,
                            note = ?,
                            consumed_at = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE domain = ?
                        """,
                        (source_job_id, note, domain),
                    )
                    reactivated += 1
                else:
                    conn.execute(
                        """
                        UPDATE spamhaus_infra_queue
                        SET source_job_id = ?,
                            note = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE domain = ?
                        """,
                        (source_job_id, note, domain),
                    )
                continue

            conn.execute(
                """
                INSERT INTO spamhaus_infra_queue (
                    domain,
                    status,
                    source,
                    source_job_id,
                    note
                ) VALUES (?, 'pending', 'spamhaus', ?, ?)
                """,
                (domain, source_job_id, note),
            )
            inserted += 1

        conn.commit()

    return {
        "queued_domains": normalized,
        "inserted": inserted,
        "reactivated": reactivated,
        "total": len(normalized),
    }


def list_spamhaus_queue(
    *,
    statuses: Sequence[str] | None = None,
    db_path: Path | str | None = None,
) -> List[dict]:
    init_polling_db(db_path)
    filters = [str(item or "").strip().lower() for item in (statuses or []) if str(item or "").strip()]
    query = """
        SELECT id, domain, status, source, source_job_id, note, queued_at, updated_at, consumed_at
        FROM spamhaus_infra_queue
    """
    params: list[str] = []
    if filters:
        placeholders = ", ".join("?" for _ in filters)
        query += f" WHERE status IN ({placeholders})"
        params.extend(filters)
    query += " ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, updated_at DESC, domain ASC"

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def mark_queue_domains_consumed(
    domains: Sequence[str],
    *,
    db_path: Path | str | None = None,
) -> int:
    normalized = normalize_domains(domains)
    if not normalized:
        return 0

    init_polling_db(db_path)
    placeholders = ", ".join("?" for _ in normalized)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"""
            UPDATE spamhaus_infra_queue
            SET status = 'consumed',
                consumed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE domain IN ({placeholders})
            """,
            normalized,
        )
        conn.commit()
        return int(cursor.rowcount or 0)
