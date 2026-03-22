import csv
import io
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from flask import Flask, Response, jsonify, render_template_string, request
from tools.spamhouse import (
    AccountRotator,
    ProviderUnavailableError,
    RetryableProviderError,
    build_domain_reputation_result,
    clean_domain,
    make_empty_domain_result,
)

ACCOUNTS = [
    {
        "username": "wkbehjan@51433850",
        "password": ":uFsEwjXGXVL917T",
        "label": "sales@evilbpserv.com",
    },
    {
        "username": "udlxkkip@65627403",
        "password": "Ds1Be9X*uZopOPDN",
        "label": "david@c-trade.ca",
    },
]
MAX_REQUESTS_PER_ACCOUNT = 250
POLL_CLEANUP_AFTER_SECONDS = 60 * 60
JOB_NOT_FOUND_TTL_SECONDS = 24 * 60 * 60
RETRY_SCHEDULE_SECONDS = [10] * 10 + [30] * 10 + [60] * 10 + [300]
MAX_TOTAL_ATTEMPTS = 31
DB_PATH = "spamhaus_cache.db"

app = Flask(__name__)

jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()
db_lock = threading.Lock()


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with db_lock:
        with db_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS domain_cache (
                    domain TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    domain_created TEXT,
                    expiration_date TEXT,
                    registrar TEXT,
                    reputation_score TEXT,
                    reputation_score_raw TEXT,
                    human TEXT,
                    identity TEXT,
                    infra TEXT,
                    malware TEXT,
                    smtp TEXT,
                    is_listed TEXT,
                    listed_until TEXT,
                    error TEXT,
                    raw_payload TEXT,
                    checked_at INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'api'
                )
                """
            )
            conn.commit()


def get_cached_domain_result(domain: str) -> Optional[Dict[str, Any]]:
    with db_lock:
        with db_connection() as conn:
            row = conn.execute(
                """
                SELECT domain, status, domain_created, expiration_date, registrar,
                       reputation_score, reputation_score_raw, human, identity, infra,
                       malware, smtp, is_listed, listed_until, error, checked_at, source
                FROM domain_cache
                WHERE domain = ?
                """,
                (domain,),
            ).fetchone()
    if not row:
        return None

    result = dict(row)
    result["cached"] = True
    result["cache_checked_at"] = row["checked_at"]
    return result


def upsert_cached_domain_result(result: Dict[str, Any], raw_payload: Optional[Dict[str, Any]] = None, source: str = "api") -> None:
    payload_text = json.dumps(raw_payload or {}, ensure_ascii=False)
    now_ts = int(time.time())
    with db_lock:
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO domain_cache (
                    domain, status, domain_created, expiration_date, registrar,
                    reputation_score, reputation_score_raw, human, identity, infra,
                    malware, smtp, is_listed, listed_until, error, raw_payload,
                    checked_at, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    status = excluded.status,
                    domain_created = excluded.domain_created,
                    expiration_date = excluded.expiration_date,
                    registrar = excluded.registrar,
                    reputation_score = excluded.reputation_score,
                    reputation_score_raw = excluded.reputation_score_raw,
                    human = excluded.human,
                    identity = excluded.identity,
                    infra = excluded.infra,
                    malware = excluded.malware,
                    smtp = excluded.smtp,
                    is_listed = excluded.is_listed,
                    listed_until = excluded.listed_until,
                    error = excluded.error,
                    raw_payload = excluded.raw_payload,
                    checked_at = excluded.checked_at,
                    source = excluded.source
                """,
                (
                    result.get("domain", ""),
                    result.get("status", "error"),
                    result.get("domain_created", "N/A"),
                    result.get("expiration_date", "N/A"),
                    result.get("registrar", "N/A"),
                    result.get("reputation_score", "N/A"),
                    str(result.get("reputation_score_raw", "")) if result.get("reputation_score_raw") is not None else "",
                    result.get("human", "N/A"),
                    result.get("identity", "N/A"),
                    result.get("infra", "N/A"),
                    result.get("malware", "N/A"),
                    result.get("smtp", "N/A"),
                    result.get("is_listed", "N/A"),
                    result.get("listed_until", "N/A"),
                    result.get("error", ""),
                    payload_text,
                    now_ts,
                    source,
                ),
            )
            conn.commit()


def is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (RetryableProviderError, ProviderUnavailableError)):
        return True
    return False


def get_retry_delay(attempt_index: int) -> int:
    if attempt_index < len(RETRY_SCHEDULE_SECONDS):
        return RETRY_SCHEDULE_SECONDS[attempt_index]
    return RETRY_SCHEDULE_SECONDS[-1]


def build_missing_job_payload(job_id: str) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "status": "missing",
        "total": 0,
        "processed": 0,
        "progress": 0,
        "current_domain": "",
        "results": [],
        "summary": {"ok": 0, "not_found": 0, "error": 0, "total_results": 0},
        "created_at": time.time(),
        "account_usage": [],
        "error_message": "",
        "resume_after_seconds": 0,
        "retry_stage": "",
        "cache_hits": 0,
        "api_checks": 0,
    }



def update_job(job_id: str, **kwargs: Any) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)



def append_result(job_id: str, result: Dict[str, Any]) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["results"].append(result)
            jobs[job_id]["summary"] = build_summary(jobs[job_id]["results"])



def build_summary(results: List[Dict[str, Any]]) -> Dict[str, int]:
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    nf_count = sum(1 for r in results if r.get("status") == "not_found")
    err_count = sum(1 for r in results if r.get("status") == "error")
    cached_count = sum(1 for r in results if r.get("cached"))
    return {
        "ok": ok_count,
        "not_found": nf_count,
        "error": err_count,
        "cached": cached_count,
        "total_results": len(results),
    }



def cleanup_old_jobs() -> None:
    while True:
        time.sleep(300)
        now = time.time()
        with jobs_lock:
            old_job_ids = []
            for job_id, job in jobs.items():
                created_at = job.get("created_at", now)
                status = job.get("status")
                ttl = JOB_NOT_FOUND_TTL_SECONDS if status in ("completed", "failed", "missing") else POLL_CLEANUP_AFTER_SECONDS
                if now - created_at > ttl:
                    old_job_ids.append(job_id)
            for job_id in old_job_ids:
                jobs.pop(job_id, None)



def call_with_backoff(job_id: str, operation_name: str, fn, *args, **kwargs) -> Any:
    last_error = None
    for attempt in range(MAX_TOTAL_ATTEMPTS):
        try:
            if attempt > 0:
                update_job(
                    job_id,
                    status="running",
                    retry_stage="",
                    resume_after_seconds=0,
                    error_message="",
                )
            return fn(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if not is_retryable_exception(exc):
                raise
            delay = get_retry_delay(attempt)
            stage = f"Retrying {operation_name}"
            update_job(
                job_id,
                status="waiting_retry",
                retry_stage=stage,
                resume_after_seconds=delay,
                error_message="",
            )
            time.sleep(delay)
    raise ProviderUnavailableError(f"{operation_name} failed after repeated retries: {last_error}")



def safe_domain_step(job_id: str, client: AccountRotator, domain: str) -> Dict[str, Any]:
    cached = get_cached_domain_result(domain)
    if cached:
        cached["cached"] = True
        return cached

    try:
        general = call_with_backoff(job_id, f"general lookup for {domain}", client.get_domain_general, domain)
        if not general:
            result = make_empty_domain_result(domain, "not_found", "No data found")
            upsert_cached_domain_result(result, {"general": {}, "dimensions": {}, "listing": {}}, source="api")
            return result

        dimensions = {}
        listing = {}
        partial_errors: List[str] = []

        try:
            dimensions = call_with_backoff(job_id, f"dimensions lookup for {domain}", client.get_domain_dimensions, domain)
        except Exception as exc:
            dimensions = {}
            partial_errors.append(f"dimensions failed: {exc}")

        try:
            listing = call_with_backoff(job_id, f"listing lookup for {domain}", client.get_domain_listing, domain)
        except Exception as exc:
            listing = {}
            partial_errors.append(f"listing failed: {exc}")

        result = build_domain_reputation_result(domain, general, dimensions, listing)
        if partial_errors:
            result["error"] = " | ".join(partial_errors)
        upsert_cached_domain_result(result, {"general": general, "dimensions": dimensions, "listing": listing}, source="api")
        return result
    except Exception as exc:
        result = make_empty_domain_result(domain, "error", str(exc))
        upsert_cached_domain_result(result, {"general": {}, "dimensions": {}, "listing": {}}, source="api")
        return result



def process_domains(job_id: str, domains: List[str]) -> None:
    try:
        client = AccountRotator(ACCOUNTS, MAX_REQUESTS_PER_ACCOUNT)
        total = len(domains)
        cache_hits = 0
        api_checks = 0
        update_job(
            job_id,
            status="running",
            total=total,
            processed=0,
            progress=0,
            current_domain="",
            account_usage=client.get_usage_snapshot(),
            error_message="",
            resume_after_seconds=0,
            retry_stage="",
            cache_hits=0,
            api_checks=0,
        )

        for index, domain in enumerate(domains, start=1):
            update_job(
                job_id,
                current_domain=domain,
                status="running",
                resume_after_seconds=0,
                retry_stage="",
                error_message="",
            )
            result = safe_domain_step(job_id, client, domain)
            if result.get("cached"):
                cache_hits += 1
            else:
                api_checks += 1
            append_result(job_id, result)
            update_job(
                job_id,
                processed=index,
                progress=int((index / total) * 100),
                account_usage=client.get_usage_snapshot(),
                status="running",
                resume_after_seconds=0,
                retry_stage="",
                error_message="",
                cache_hits=cache_hits,
                api_checks=api_checks,
            )

        update_job(
            job_id,
            status="completed",
            current_domain="",
            account_usage=client.get_usage_snapshot(),
            resume_after_seconds=0,
            retry_stage="",
            error_message="",
            cache_hits=cache_hits,
            api_checks=api_checks,
        )
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            current_domain="",
            error_message=f"Background worker failed unexpectedly: {exc}",
            resume_after_seconds=0,
            retry_stage="",
        )


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Spamhaus Domain Dashboard</title>
    <style>
        :root {
            --bg: #071120;
            --panel: #0d1a2d;
            --panel-2: #11233c;
            --border: #1f3a5c;
            --text: #e7eefc;
            --muted: #9ab0d0;
            --green: #1fd47a;
            --red: #ff5d6c;
            --yellow: #ffc44d;
            --blue: #53a6ff;
            --white: #ffffff;
            --shadow: 0 10px 35px rgba(0, 0, 0, 0.28);
        }

        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background:
                radial-gradient(circle at top left, rgba(39, 112, 255, 0.12), transparent 28%),
                linear-gradient(180deg, #06101d 0%, #091628 100%);
            color: var(--text);
        }

        .container {
            width: min(1600px, calc(100% - 20px));
            margin: 10px auto;
        }

        .card {
            background: rgba(12, 24, 43, 0.94);
            border: 1px solid rgba(83, 166, 255, 0.13);
            border-radius: 16px;
            box-shadow: var(--shadow);
            padding: 16px;
            margin-bottom: 14px;
        }

        .hero {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 14px;
        }

        .title { font-size: 26px; font-weight: 800; margin-bottom: 8px; }
        .subtitle, .hint { color: var(--muted); font-size: 13px; line-height: 1.45; }
        textarea {
            width: 100%; min-height: 150px; resize: vertical; margin-top: 12px;
            border: 1px solid var(--border); background: #081425; color: var(--text);
            border-radius: 12px; padding: 12px; outline: none; font-size: 14px;
        }
        .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
        button {
            border: 0; border-radius: 10px; padding: 10px 14px; cursor: pointer;
            color: white; font-size: 14px; font-weight: 700;
        }
        .primary { background: linear-gradient(90deg, #1a73ff, #3d9bff); }
        .secondary { background: linear-gradient(90deg, #23415f, #31577c); }
        button:disabled { opacity: .55; cursor: not-allowed; }

        .stats-grid, .summary-row {
            display: grid; gap: 10px;
            grid-template-columns: repeat(6, minmax(0, 1fr));
        }
        .stat-box, .summary-pill {
            background: linear-gradient(180deg, rgba(18, 36, 61, 0.98), rgba(10, 22, 37, 0.98));
            border: 1px solid rgba(83, 166, 255, 0.12);
            border-radius: 12px; padding: 12px;
        }
        .stat-label, .summary-pill .label { color: var(--muted); font-size: 12px; margin-bottom: 6px; }
        .stat-value, .summary-pill .value { font-size: 22px; font-weight: 800; }

        .progress-wrap { margin-top: 14px; }
        .progress-track {
            width: 100%; height: 12px; border-radius: 999px; overflow: hidden;
            background: #0a1526; border: 1px solid var(--border);
        }
        .progress-bar {
            height: 100%; width: 0%; background: linear-gradient(90deg, #1fd47a, #53a6ff);
            transition: width .35s ease;
        }
        .progress-meta {
            display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
            margin-top: 8px; color: var(--muted); font-size: 13px;
        }

        .results-header {
            display: flex; justify-content: space-between; align-items: center;
            gap: 14px; flex-wrap: wrap; margin-bottom: 12px;
        }
        .filter-bar {
            display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
            color: var(--muted); font-size: 13px;
        }
        .filter-pill {
            padding: 7px 10px; border-radius: 999px; border: 1px solid rgba(83,166,255,.16);
            background: rgba(255,255,255,.03); cursor: pointer; user-select: none;
        }
        .filter-pill.active { color: var(--white); border-color: rgba(83,166,255,.4); }
        .sortable { cursor: pointer; user-select: none; }
        .sortable:hover { color: var(--blue); }

        .table-wrap {
            overflow-x: auto;
            border: 1px solid rgba(83,166,255,.12);
            border-radius: 14px;
            background: rgba(7, 17, 32, 0.55);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            min-width: 1500px;
        }
        thead th {
            position: sticky; top: 0; z-index: 1;
            background: linear-gradient(180deg, #324a69 0%, #2a3f59 100%);
            color: #f3f7ff; font-size: 12px; text-transform: uppercase; letter-spacing: .03em;
            padding: 8px 6px; border-right: 1px solid rgba(255,255,255,.10); white-space: nowrap;
        }
        tbody td {
            padding: 7px 6px; border-top: 1px solid rgba(255,255,255,.06);
            border-right: 1px solid rgba(255,255,255,.05); font-size: 13px;
            text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        tbody tr:hover { background: rgba(83,166,255,.06); }
        td.domain-cell {
            text-align: left; color: #ffefe8; font-weight: 700;
        }
        .status-text-ok { color: var(--green); font-weight: 700; }
        .status-text-nf { color: var(--yellow); font-weight: 700; }
        .status-text-err { color: var(--red); font-weight: 700; }
        .score-positive { color: var(--green); font-weight: 800; }
        .score-negative { color: var(--red); font-weight: 800; }
        .score-zero { color: var(--white); font-weight: 800; }
        .listed-yes { color: var(--red); font-weight: 700; }
        .listed-no { color: var(--green); font-weight: 700; }
        .tiny-dot {
            display: inline-block; width: 8px; height: 8px; border-radius: 50%;
            vertical-align: middle;
        }
        .dot-green { background: var(--green); box-shadow: 0 0 0 2px rgba(31,212,122,.18) inset; }
        .dot-red { background: var(--red); box-shadow: 0 0 0 2px rgba(255,93,108,.18) inset; }
        .cell-expand { cursor: pointer; }
        .expanded-cell {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
            word-break: break-word;
            line-height: 1.35;
        }
        .cached-pill {
            display: inline-block;
            margin-left: 6px;
            padding: 2px 6px;
            border-radius: 999px;
            font-size: 10px;
            font-weight: 700;
            color: #0b1220;
            background: var(--yellow);
        }
        .empty-state {
            padding: 28px; text-align: center; color: var(--muted);
            border: 1px dashed rgba(83,166,255,.18); border-radius: 14px;
            background: rgba(255,255,255,.02);
        }

        .w-domain{width:260px}.w-s{width:72px}.w-m{width:94px}.w-l{width:120px}.w-xl{width:170px}

        @media (max-width: 1180px) {
            .hero { grid-template-columns: 1fr; }
            .stats-grid, .summary-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        }
        @media (max-width: 700px) {
            .stats-grid, .summary-row { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card hero">
            <div>
                <div class="title">Spamhaus Domain Dashboard</div>
                <div class="subtitle">Paste one domain per line. Results are cached locally in SQLite, so previously checked domains return instantly without new API requests.</div>
                <textarea id="domains" placeholder="llavedecobre.com&#10;example.com&#10;google.com"></textarea>
                <div class="toolbar">
                    <button id="startBtn" class="primary">Start Scan</button>
                    <button id="downloadBtn" class="secondary" style="display:none;">Download CSV</button>
                </div>
                <div class="hint" style="margin-top:8px;">Click any long cell to expand it vertically without breaking the full row layout.</div>
            </div>
            <div>
                <div class="stats-grid">
                    <div class="stat-box"><div class="stat-label">Status</div><div class="stat-value" id="jobStatus">Idle</div></div>
                    <div class="stat-box"><div class="stat-label">Total</div><div class="stat-value" id="totalDomains">0</div></div>
                    <div class="stat-box"><div class="stat-label">Processed</div><div class="stat-value" id="processedDomains">0</div></div>
                    <div class="stat-box"><div class="stat-label">Progress</div><div class="stat-value" id="progressPercent">0%</div></div>
                    <div class="stat-box"><div class="stat-label">Cache Hits</div><div class="stat-value" id="cacheHits">0</div></div>
                    <div class="stat-box"><div class="stat-label">API Checks</div><div class="stat-value" id="apiChecks">0</div></div>
                </div>
                <div class="progress-wrap">
                    <div class="progress-track"><div id="progressBar" class="progress-bar"></div></div>
                    <div class="progress-meta">
                        <span id="progressText">Waiting to start...</span>
                        <span id="currentDomain"></span>
                    </div>
                </div>
                <div class="hint" style="margin-top:10px;">Account usage rotates automatically after each account reaches its configured request budget.</div>
                <div id="accountUsage" class="hint" style="margin-top:8px;">No account usage yet.</div>
                <div id="retryStatus" class="hint" style="margin-top:8px;"></div>
            </div>
        </div>

        <div class="card">
            <div class="results-header">
                <div>
                    <h2 style="margin:0 0 6px 0;">Results</h2>
                    <div class="hint">Dense one-page table layout with local DB cache support.</div>
                </div>
                <div class="filter-bar">
                    <span>Show Filter</span>
                    <span class="filter-pill active" data-filter="all">All</span>
                    <span class="filter-pill" data-filter="ok">OK</span>
                    <span class="filter-pill" data-filter="not_found">Not Found</span>
                    <span class="filter-pill" data-filter="error">Error</span>
                </div>
            </div>

            <div class="summary-row" style="margin-bottom:12px;">
                <div class="summary-pill"><div class="label">OK</div><div class="value" id="sumOk">0</div></div>
                <div class="summary-pill"><div class="label">Not Found</div><div class="value" id="sumNotFound">0</div></div>
                <div class="summary-pill"><div class="label">Errors</div><div class="value" id="sumError">0</div></div>
                <div class="summary-pill"><div class="label">Cached Rows</div><div class="value" id="sumCached">0</div></div>
                <div class="summary-pill"><div class="label">Visible Rows</div><div class="value" id="sumRendered">0</div></div>
                <div class="summary-pill"><div class="label">DB File</div><div class="value" style="font-size:14px;">spamhaus_cache.db</div></div>
            </div>

            <div id="resultsContainer">
                <div class="empty-state">No results yet.</div>
            </div>
        </div>
    </div>

    <script>
        const apiBase = {{ api_base|tojson }};
        let currentJobId = null;
        let latestResults = [];
        let currentSort = { key: null, direction: 'asc' };
        let currentFilter = 'all';
        let consecutivePollErrors = 0;
        let pollDelay = 1000;
        let pollTimer = null;

        function escapeHtml(value) {
            if (value === null || value === undefined) return '';
            return String(value)
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#039;');
        }

        function parseNumeric(value) {
            if (value === null || value === undefined || value === 'N/A' || value === '-') return null;
            const n = Number(value);
            return Number.isFinite(n) ? n : null;
        }

        function parseDateValue(value) {
            if (!value || value === 'N/A') return null;
            const parts = String(value).split('/');
            if (parts.length !== 3) return null;
            const [mm, dd, yyyy] = parts.map(Number);
            if (!mm || !dd || !yyyy) return null;
            return new Date(yyyy, mm - 1, dd).getTime();
        }

        function scoreClass(value) {
            const n = parseNumeric(value);
            if (n === null || n === 0) return 'score-zero';
            return n > 0 ? 'score-positive' : 'score-negative';
        }

        function listedClass(value) {
            const raw = String(value).toLowerCase();
            if (raw === 'true' || raw === 'yes') return 'listed-yes';
            if (raw === 'false' || raw === 'no') return 'listed-no';
            return '';
        }

        function statusText(status) {
            if (status === 'ok') return '<span class="status-text-ok">available</span>';
            if (status === 'not_found') return '<span class="status-text-nf">not found</span>';
            if (status === 'missing') return '<span class="status-text-nf">missing</span>';
            return '<span class="status-text-err">error</span>';
        }

        function boolDot(value) {
            const raw = String(value).toLowerCase();
            const green = ['false', 'no', '0', 'n/a', '-'].includes(raw) || raw === '';
            return `<span class="tiny-dot ${green ? 'dot-green' : 'dot-red'}"></span>`;
        }

        function compareValues(a, b, key) {
            const dateKeys = ['domain_created', 'expiration_date', 'listed_until'];
            const numericKeys = ['reputation_score', 'human', 'identity', 'infra', 'malware', 'smtp'];
            if (dateKeys.includes(key)) {
                const av = parseDateValue(a[key]);
                const bv = parseDateValue(b[key]);
                if (av === null && bv === null) return 0;
                if (av === null) return 1;
                if (bv === null) return -1;
                return av - bv;
            }
            if (numericKeys.includes(key)) {
                const av = parseNumeric(a[key]);
                const bv = parseNumeric(b[key]);
                if (av === null && bv === null) return 0;
                if (av === null) return 1;
                if (bv === null) return -1;
                return av - bv;
            }
            const as = String(a[key] || '').toLowerCase();
            const bs = String(b[key] || '').toLowerCase();
            return as.localeCompare(bs);
        }

        function getFilteredResults() {
            let rows = [...latestResults];
            if (currentFilter !== 'all') {
                rows = rows.filter(r => r.status === currentFilter);
            }
            if (currentSort.key) {
                rows.sort((a, b) => compareValues(a, b, currentSort.key));
                if (currentSort.direction === 'desc') rows.reverse();
            }
            return rows;
        }

        function th(label, key, klass='w-m') {
            const arrow = currentSort.key === key ? (currentSort.direction === 'asc' ? ' ↑' : ' ↓') : '';
            return `<th class="${klass} sortable" data-sort="${key}">${label}${arrow}</th>`;
        }

        function td(value, klass='') {
            return `<td class="cell-expand ${klass}" title="Click to expand">${escapeHtml(value ?? 'N/A')}</td>`;
        }

        function renderResults(results) {
            latestResults = Array.isArray(results) ? [...results] : latestResults;
            const rows = getFilteredResults();
            const wrap = document.getElementById('resultsContainer');

            if (!rows.length) {
                wrap.innerHTML = '<div class="empty-state">No rows match the current filter.</div>';
                document.getElementById('sumRendered').textContent = '0';
                return;
            }

            wrap.innerHTML = `
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                ${th('Domain', 'domain', 'w-domain')}
                                ${th('Created', 'domain_created', 'w-m')}
                                ${th('Expires', 'expiration_date', 'w-m')}
                                ${th('Registrar', 'registrar', 'w-xl')}
                                ${th('Score', 'reputation_score', 'w-s')}
                                ${th('Human', 'human', 'w-s')}
                                ${th('Identity', 'identity', 'w-s')}
                                ${th('Infra', 'infra', 'w-s')}
                                ${th('Malware', 'malware', 'w-s')}
                                ${th('SMTP', 'smtp', 'w-s')}
                                <th class="w-s">Listed</th>
                                ${th('Listed Until', 'listed_until', 'w-m')}
                                ${th('Status', 'status', 'w-m')}
                                <th class="w-s">Cache</th>
                                <th class="w-xl">Info</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows.map((row) => `
                                <tr>
                                    <td class="domain-cell cell-expand" title="Click to expand">${escapeHtml(row.domain)}${row.cached ? '<span class="cached-pill">cached</span>' : ''}</td>
                                    ${td(row.domain_created)}
                                    ${td(row.expiration_date)}
                                    ${td(row.registrar)}
                                    <td class="${scoreClass(row.reputation_score)}">${escapeHtml(row.reputation_score || 'N/A')}</td>
                                    ${td(row.human)}
                                    ${td(row.identity)}
                                    ${td(row.infra)}
                                    ${td(row.malware)}
                                    ${td(row.smtp)}
                                    <td class="${listedClass(row.is_listed)}">${boolDot(row.is_listed)}&nbsp;${escapeHtml(row.is_listed)}</td>
                                    ${td(row.listed_until)}
                                    <td>${statusText(row.status)}</td>
                                    <td>${row.cached ? '<span class="status-text-ok">hit</span>' : '<span class="status-text-nf">api</span>'}</td>
                                    <td class="cell-expand ${row.error ? 'status-text-err' : ''}" title="Click to expand">${escapeHtml(row.error || '-')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;

            document.querySelectorAll('[data-sort]').forEach((el) => {
                el.addEventListener('click', () => {
                    const key = el.dataset.sort;
                    if (currentSort.key === key) {
                        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                    } else {
                        currentSort = { key, direction: 'asc' };
                    }
                    renderResults(latestResults);
                });
            });

            document.querySelectorAll('.cell-expand').forEach((el) => {
                el.addEventListener('click', () => {
                    el.classList.toggle('expanded-cell');
                });
            });

            document.getElementById('sumRendered').textContent = String(rows.length);
        }

        function updateSummary(summary) {
            document.getElementById('sumOk').textContent = String(summary?.ok || 0);
            document.getElementById('sumNotFound').textContent = String(summary?.not_found || 0);
            document.getElementById('sumError').textContent = String(summary?.error || 0);
            document.getElementById('sumCached').textContent = String(summary?.cached || 0);
        }

        function getPollDelay(attempt) {
            if (attempt < 10) return 10000;
            if (attempt < 20) return 30000;
            if (attempt < 30) return 60000;
            return 300000;
        }

        function scheduleNextPoll() {
            if (!currentJobId) return;
            clearTimeout(pollTimer);
            pollTimer = setTimeout(() => {
                fetchJob(currentJobId)
                    .then(() => {
                        consecutivePollErrors = 0;
                        pollDelay = 1000;
                        const status = document.getElementById('jobStatus').textContent;
                        if (currentJobId && status !== 'completed' && status !== 'failed' && status !== 'missing') {
                            scheduleNextPoll();
                        }
                    })
                    .catch(() => {
                        consecutivePollErrors += 1;
                        pollDelay = getPollDelay(consecutivePollErrors - 1);
                        document.getElementById('retryStatus').textContent = `Connection issue. Retrying dashboard sync in ${Math.floor(pollDelay / 1000)}s.`;
                        scheduleNextPoll();
                    });
            }, pollDelay);
        }

        function updateDashboard(job) {
            document.getElementById('jobStatus').textContent = job.status || 'unknown';
            document.getElementById('totalDomains').textContent = String(job.total || 0);
            document.getElementById('processedDomains').textContent = String(job.processed || 0);
            document.getElementById('progressPercent').textContent = `${job.progress || 0}%`;
            document.getElementById('progressText').textContent = `Processed ${job.processed || 0} of ${job.total || 0}`;
            document.getElementById('currentDomain').textContent = job.current_domain ? `Current: ${job.current_domain}` : '';
            document.getElementById('progressBar').style.width = `${job.progress || 0}%`;
            document.getElementById('cacheHits').textContent = String(job.cache_hits || 0);
            document.getElementById('apiChecks').textContent = String(job.api_checks || 0);
            updateSummary(job.summary || {});

            if (Array.isArray(job.results) && job.results.length) {
                renderResults(job.results);
            } else if (!latestResults.length) {
                renderResults([]);
            }

            const usage = Array.isArray(job.account_usage) ? job.account_usage : [];
            document.getElementById('accountUsage').textContent = usage.length
                ? usage.map((entry) => `${entry.label}: total ${entry.used}, cycle ${entry.cycle_used}/250, remaining ${entry.remaining}${entry.cooldown ? ' (cooldown)' : ''}`).join(' | ')
                : 'No account usage yet.';

            if (job.status === 'waiting_retry' && (job.resume_after_seconds || 0) > 0) {
                const stage = job.retry_stage || 'Temporary provider issue';
                document.getElementById('retryStatus').textContent = `${stage}. Next retry in ${job.resume_after_seconds}s.`;
            } else {
                document.getElementById('retryStatus').textContent = '';
            }

            if (job.status === 'completed' && currentJobId) {
                document.getElementById('downloadBtn').style.display = 'inline-block';
            }
            if (job.status === 'completed' || job.status === 'failed' || job.status === 'missing') {
                clearTimeout(pollTimer);
                pollTimer = null;
                document.getElementById('startBtn').disabled = false;
            }
        }

        async function fetchJob(jobId) {
            const res = await fetch(`${apiBase}/api/job/${jobId}`);
            const data = await res.json();
            updateDashboard(data);
            return data;
        }

        document.querySelectorAll('.filter-pill').forEach((el) => {
            el.addEventListener('click', () => {
                document.querySelectorAll('.filter-pill').forEach((x) => x.classList.remove('active'));
                el.classList.add('active');
                currentFilter = el.dataset.filter;
                renderResults(latestResults);
            });
        });

        document.getElementById('startBtn').addEventListener('click', async () => {
            const domains = document.getElementById('domains').value;
            document.getElementById('startBtn').disabled = true;
            document.getElementById('downloadBtn').style.display = 'none';
            document.getElementById('retryStatus').textContent = '';
            latestResults = [];
            renderResults([]);
            updateSummary({ ok: 0, not_found: 0, error: 0, cached: 0 });
            document.getElementById('cacheHits').textContent = '0';
            document.getElementById('apiChecks').textContent = '0';
            consecutivePollErrors = 0;
            pollDelay = 1000;
            clearTimeout(pollTimer);

            try {
                const res = await fetch(`${apiBase}/api/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ domains })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Failed to start job');
                currentJobId = data.job_id;
                await fetchJob(currentJobId);
                scheduleNextPoll();
            } catch (err) {
                alert(err.message || String(err));
                document.getElementById('startBtn').disabled = false;
            }
        });

        document.getElementById('downloadBtn').addEventListener('click', () => {
            if (!currentJobId) return;
            window.location.href = `${apiBase}/api/export/${currentJobId}`;
        });
    </script>
</body>
</html>
"""


def render_index(api_base: str = "") -> str:
    normalized_api_base = (api_base or "").rstrip("/")
    return render_template_string(HTML, api_base=normalized_api_base)


@app.route("/")
def index() -> str:
    return render_index()


@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(silent=True) or {}
    raw_domains = data.get("domains", "")

    parsed_domains: List[str] = []
    seen = set()
    for line in raw_domains.splitlines():
        domain = clean_domain(line)
        if domain and domain not in seen:
            parsed_domains.append(domain)
            seen.add(domain)

    if not parsed_domains:
        return jsonify({"error": "No valid domains provided"}), 400

    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "total": len(parsed_domains),
            "processed": 0,
            "progress": 0,
            "current_domain": "",
            "results": [],
            "summary": {"ok": 0, "not_found": 0, "error": 0, "cached": 0, "total_results": 0},
            "created_at": time.time(),
            "account_usage": [],
            "error_message": "",
            "resume_after_seconds": 0,
            "retry_stage": "",
            "cache_hits": 0,
            "api_checks": 0,
        }

    thread = threading.Thread(target=process_domains, args=(job_id, parsed_domains), daemon=True)
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/api/job/<job_id>", methods=["GET"])
def api_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job:
            return jsonify(job)
        missing_job = build_missing_job_payload(job_id)
    return jsonify(missing_job)


@app.route("/api/export/<job_id>", methods=["GET"])
def api_export(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "domain",
        "status",
        "domain_created",
        "expiration_date",
        "registrar",
        "reputation_score",
        "human",
        "identity",
        "infra",
        "malware",
        "smtp",
        "is_listed",
        "listed_until",
        "cached",
        "error",
    ])

    for row in job.get("results", []):
        writer.writerow([
            row.get("domain", ""),
            row.get("status", ""),
            row.get("domain_created", ""),
            row.get("expiration_date", ""),
            row.get("registrar", ""),
            row.get("reputation_score", ""),
            row.get("human", ""),
            row.get("identity", ""),
            row.get("infra", ""),
            row.get("malware", ""),
            row.get("smtp", ""),
            row.get("is_listed", ""),
            row.get("listed_until", ""),
            row.get("cached", False),
            row.get("error", ""),
        ])

    csv_data = output.getvalue()
    output.close()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=spamhaus_results_{job_id}.csv"},
    )


if __name__ == "__main__":
    init_db()
    cleanup_thread = threading.Thread(target=cleanup_old_jobs, daemon=True)
    cleanup_thread.start()
    app.run(debug=True, host="0.0.0.0", port=5001)
