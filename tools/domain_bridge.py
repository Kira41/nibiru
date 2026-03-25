from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Sequence

from nibiru import database_path

INFRA_DB_PATH = database_path(
    "script3.db",
    Path(__file__).resolve().parent.parent / "script3.db",
)
INFRA_STORAGE_KEY = "mailInfraDashboardDataV4"


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
            CREATE TABLE IF NOT EXISTS app_storage (
                storage_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
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


def _default_infra_data() -> dict[str, Any]:
    return {
        "servers": [],
        "ips": [],
        "domains": [],
        "domainRegistry": [],
        "snapshots": [],
        "domainDraftsByIp": {},
        "namecheapConfig": {
            "apiUser": "",
            "apiKey": "",
            "username": "",
            "clientIp": "",
            "sandbox": False,
        },
    }


def _load_infra_data(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        "SELECT payload FROM app_storage WHERE storage_key = ?",
        (INFRA_STORAGE_KEY,),
    ).fetchone()
    if not row:
        return _default_infra_data()
    try:
        payload = json.loads(row["payload"])
    except Exception:
        return _default_infra_data()
    if not isinstance(payload, dict):
        return _default_infra_data()

    normalized = _default_infra_data()
    normalized.update(payload)
    if not isinstance(normalized.get("domainRegistry"), list):
        normalized["domainRegistry"] = []
    return normalized


def _save_infra_data(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO app_storage (storage_key, payload, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(storage_key) DO UPDATE SET
            payload = excluded.payload,
            updated_at = CURRENT_TIMESTAMP
        """,
        (INFRA_STORAGE_KEY, json.dumps(data, ensure_ascii=False)),
    )


def _normalize_domain(domain: str) -> str:
    return str(domain or "").strip().lower()


def _build_spamhaus_note(domain_record: dict[str, Any] | None = None) -> str:
    record = domain_record if isinstance(domain_record, dict) else {}
    pushed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    fields = [
        ("Status", record.get("status")),
        ("Reputation score", record.get("reputation_score")),
        ("Created", record.get("domain_created")),
        ("Expiration", record.get("expiration_date")),
        ("Registrar", record.get("registrar")),
        ("Human", record.get("human")),
        ("Identity", record.get("identity")),
        ("Infra", record.get("infra")),
        ("Malware", record.get("malware")),
        ("SMTP", record.get("smtp")),
        ("Listed", record.get("is_listed")),
        ("Listed until", record.get("listed_until")),
        ("Error", record.get("error")),
        ("Source job", record.get("source_job_id") or record.get("job_id")),
        ("Cache source", record.get("source")),
    ]
    details = [
        f"{label}: {str(value).strip()}"
        for label, value in fields
        if str(value or "").strip() and str(value).strip().lower() not in {"n/a", "none"}
    ]
    base = f"Push it from spamhost Shaker | pushed_at: {pushed_at}"
    if not details:
        return base
    return base + " | " + " | ".join(details)


def sync_spamhaus_domains_to_infra_registry(
    domains: Sequence[str],
    *,
    domain_records: Sequence[dict[str, Any]] | None = None,
    db_path: Path | str | None = None,
) -> dict[str, int]:
    normalized = normalize_domains(domains)
    if not normalized:
        return {"inserted": 0, "updated": 0}

    records_by_domain = {
        _normalize_domain(item.get("domain")): item
        for item in (domain_records or [])
        if isinstance(item, dict) and _normalize_domain(item.get("domain"))
    }
    inserted = 0
    updated = 0

    with _connect(db_path) as conn:
        data = _load_infra_data(conn)
        registry = data.setdefault("domainRegistry", [])
        existing_by_domain = {}
        for entry in registry:
            if isinstance(entry, dict):
                normalized_domain = _normalize_domain(entry.get("domain"))
                if normalized_domain and normalized_domain not in existing_by_domain:
                    existing_by_domain[normalized_domain] = entry

        changed = False
        for domain in normalized:
            note = _build_spamhaus_note(records_by_domain.get(domain))
            existing = existing_by_domain.get(domain)
            if existing:
                new_note = note if not str(existing.get("note") or "").strip() else f"{existing['note']}\n{note}"
                if existing.get("note") != new_note:
                    existing["note"] = new_note
                    changed = True
                    updated += 1
                if not str(existing.get("provider") or "").strip():
                    existing["provider"] = "spamhostshaker"
                    changed = True
                if "linkedIpId" not in existing:
                    existing["linkedIpId"] = ""
                    changed = True
                continue

            registry.append(
                {
                    "id": f"regdom_{uuid.uuid4().hex[:12]}",
                    "domain": domain,
                    "provider": "spamhostshaker",
                    "expiryDate": "",
                    "accountUser": "",
                    "linkedIpId": "",
                    "note": note,
                }
            )
            inserted += 1
            changed = True

        if changed:
            _save_infra_data(conn, data)
            conn.commit()

    return {"inserted": inserted, "updated": updated}


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
    domain_records: Sequence[dict[str, Any]] | None = None,
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

    sync_result = sync_spamhaus_domains_to_infra_registry(
        normalized,
        domain_records=domain_records,
        db_path=db_path,
    )

    return {
        "queued_domains": normalized,
        "inserted": inserted,
        "reactivated": reactivated,
        "infra_registry_inserted": sync_result["inserted"],
        "infra_registry_updated": sync_result["updated"],
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
