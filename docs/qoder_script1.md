# script1.py - Sender Domain Screening (Spamhaus)

## Overview

`script1.py` is the sender-domain screening tool. It checks candidate sender domains against the Spamhaus Intelligence API (SIA) to evaluate reputation, listing status, and WHOIS data. Results are cached in a local SQLite database.

**File size:** ~53KB
**Role:** Sender-side qualification tool.

---

## Dependencies

- **Flask** - Web framework
- **tools.spamhouse** - `AccountRotator`, `build_domain_reputation_result`, `clean_domain`, `make_empty_domain_result`, `RetryableProviderError`, `ProviderUnavailableError`
- **tools.domain_bridge** - `enqueue_spamhaus_domains`, `init_polling_db`
- **nibiru** - `database_path`

---

## Flask Routes

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/` | GET | `index()` | Renders HTML dashboard with Spamhaus scanning UI |
| `/api/start` | POST | `api_start()` | Creates a new screening job, spawns background thread |
| `/api/job/<job_id>` | GET | `api_job()` | Returns current job status, progress, and results |
| `/api/cache-results` | GET | `api_cache_results()` | Loads all cached domain results from SQLite |
| `/api/poll-infra` | POST | `api_poll_infra()` | Queues selected domains into infrastructure polling |
| `/api/export/<job_id>` | GET | `api_export()` | Exports job results as CSV |

---

## Global Configuration

| Variable | Value | Purpose |
|----------|-------|---------|
| `ACCOUNTS` | 2 Spamhaus API accounts | Credentials for API rotation |
| `MAX_REQUESTS_PER_ACCOUNT` | 250 | Per-account request budget per cycle |
| `POLL_CLEANUP_AFTER_SECONDS` | 3600 | TTL for pending jobs |
| `JOB_NOT_FOUND_TTL_SECONDS` | 86400 | 24-hour TTL for completed/failed jobs |
| `RETRY_SCHEDULE_SECONDS` | 10x10s + 10x30s + 10x60s + 1x300s | Backoff schedule |
| `MAX_TOTAL_ATTEMPTS` | 31 | Max retries before permanent failure |
| `DB_PATH` | `database/spamhaus_cache.db` | SQLite cache database |

---

## Database Schema

### Table: `domain_cache`

| Column | Type | Purpose |
|--------|------|---------|
| `domain` | TEXT PRIMARY KEY | Normalized domain name |
| `status` | TEXT NOT NULL | `ok`, `not_found`, or `error` |
| `domain_created` | TEXT | Creation date (mm/dd/yyyy) |
| `expiration_date` | TEXT | Expiry date (mm/dd/yyyy) |
| `registrar` | TEXT | Domain registrar |
| `reputation_score` | TEXT | Formatted reputation score |
| `reputation_score_raw` | TEXT | Raw numeric score |
| `human` | TEXT | Human dimension score |
| `identity` | TEXT | Identity dimension score |
| `infra` | TEXT | Infrastructure dimension score |
| `malware` | TEXT | Malware dimension score |
| `smtp` | TEXT | SMTP dimension score |
| `is_listed` | TEXT | Blacklist status |
| `listed_until` | TEXT | Listing expiry date |
| `error` | TEXT | Error message if applicable |
| `raw_payload` | TEXT | JSON blob of raw API responses |
| `checked_at` | INTEGER NOT NULL | Unix timestamp of last check |
| `source` | TEXT NOT NULL DEFAULT 'api' | `api` or `cache` |

---

## Background Job System

### Job States

`queued` -> `running` -> `completed` | `failed` | `missing`

During retry: `waiting_retry` with countdown.

### Job Record Structure

```python
{
    "job_id": str,
    "status": str,
    "total": int,
    "processed": int,
    "progress": int,           # percentage 0-100
    "current_domain": str,
    "results": list,
    "summary": dict,           # ok/not_found/error/cached/total counts
    "created_at": str,
    "account_usage": list,
    "error_message": str,
    "resume_after_seconds": int,
    "retry_stage": str,
    "cache_hits": int,
    "api_checks": int,
}
```

### Processing Flow

1. `POST /api/start` - Parse domains, deduplicate, create job, spawn thread
2. Background thread creates `AccountRotator` with configured accounts
3. For each domain:
   - Check SQLite cache first (cache hit -> skip API)
   - Call Spamhaus API: `get_domain_general()`, `get_domain_dimensions()`, `get_domain_listing()`
   - Build result via `build_domain_reputation_result()`
   - Upsert to SQLite cache
   - Update job progress
4. Set job status to `completed` or `failed`

### Retry & Backoff

- Retryable errors: timeouts, 429, 5xx responses
- Schedule: 10x10s, 10x30s, 10x60s, 1x300s (max ~16.7 minutes total)
- Account rotation: on 429, sets account to cooldown, rotates to next
- Cycle reset: when all accounts exhausted, counters reset

### Cleanup Thread

- Daemon thread runs every 300s
- Removes expired jobs (completed/failed: 24h TTL, pending: 1h TTL)

---

## Spamhaus API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/login` | Authenticate and get bearer token |
| `GET /api/intel/v2/byobject/domain/{domain}` | General domain info (WHOIS, score, tags) |
| `GET /api/intel/v2/byobject/domain/{domain}/dimensions` | Dimension scores (human, identity, infra, malware, smtp) |
| `GET /api/intel/v2/byobject/domain/{domain}/listing` | Blacklist listing status |

---

## Infrastructure Bridge

`POST /api/poll-infra` sends selected domains to the infrastructure queue via `enqueue_spamhaus_domains()`:
- Inserts into `spamhaus_infra_queue` table
- Syncs to infrastructure domain registry in script3's database
- Returns queued count and registry sync results

---

## Frontend Features

- Real-time polling (1-10s adaptive interval)
- Result table with 15 sortable columns
- Status filtering (All/OK/Not Found/Error)
- Domain selection for infrastructure polling
- CSV export
- Cached DB viewer (load all historical results)
- Account usage display with cooldown status
- Retry countdown display
