# nibiru.py - Unified Shell & Integration Target

## Overview

`nibiru.py` is the primary application entrypoint and unified operator shell for the Nibiru project. It aggregates all sub-tools (script1 through script6) under a single Flask application with a shared navigation bar, unified routing, and centralized database path management.

**File size:** ~300KB
**Role:** Unified application shell, active mailer surface, and first integration target.

---

## Dependencies

- **Flask** - Web framework
- **script1** through **script6** - Sub-tool modules
- **tools.dns_shaker.DNSShaker** - DNS record auditing

---

## Key Architectural Functions

### `database_path(filename, *legacy_candidates)`

Central database path resolver used by all modules. Ensures all databases live under `database/`.

**Logic:**
1. Compute target: `DATABASE_DIR / filename`
2. If target exists, return it
3. For each legacy candidate: if found, migrate via `shutil.move()` to target
4. Return target path (directory auto-created)

### `ensure_database_dir()`

Creates the `database/` directory if it does not exist.

---

## Navigation System

All pages share a fixed top navigation bar injected via `inject_nibiru_navbar(html, active_page)`.

**Navigation items:**

| Label | Path | Target |
|-------|------|--------|
| Dashboard | `/` | Main dashboard |
| Spamhaus | `/spamhaus` | `/tools/spamhaus/` |
| Infra | `/infra` | `/tools/infra/` |
| Extractor | `/extractor` | `/tools/extractor/` |
| Campaigns | `/campaigns` | Campaign list |
| Send | `/send` | Campaign send page |
| Jobs | `/jobs` | Job monitoring |
| Tracker | `/tracker` | `/tools/tracker/` |
| Accounting | `/accounting` | PMTA analytics |

**Design:** Dark theme (`rgba(6,12,24,.94)`), backdrop blur, fixed position, responsive layout.

---

## Flask Routes

### Dashboard & Navigation

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/` | GET | `index()` | Dashboard home with KPIs, campaign summary, alerts |
| `/img/<path:filename>` | GET | - | Static image serving from `img/` |

### Campaign Management

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/send` | GET | - | Send page (campaign form) |
| `/campaigns` | GET | - | Campaign list with filtering and search |
| `/campaigns/create` | POST | - | Create new campaign |
| `/campaigns/<id>/rename` | POST | - | Rename campaign |
| `/campaigns/<id>/delete` | POST | - | Delete campaign |
| `/campaigns/delete-filtered` | POST | - | Batch delete by filter |
| `/campaign/<id>` | GET | - | Campaign detail (redirects to send) |

### Campaign API

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/api/campaign/<id>/form` | GET | - | Fetch campaign form state |
| `/api/campaign/<id>/form` | POST | - | Save campaign form state |
| `/api/campaign/<id>/clear` | POST | - | Clear campaign data |
| `/api/campaign/<id>/latest_job` | GET | - | Get latest job for campaign |
| `/api/campaign/<id>/domains_stats` | GET | - | Get domain statistics |

### Jobs & Monitoring

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/jobs` | GET | - | Jobs list/overview page |
| `/job/<job_id>` | GET | - | Individual job detail page |
| `/api/jobs` | GET | `api_jobs()` | Jobs API (diagnostics + list) |
| `/api/job/<job_id>` | GET | `api_job()` | Job detail API |
| `/api/job/<job_id>/control` | POST | - | Job control (pause/resume/stop) |

### Dashboard API

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/api/dashboard` | GET | - | Dashboard live snapshot |
| `/api/preflight` | POST | - | Preflight check (spam score, DNS, listings) |

### Accounting

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/accounting` | GET | - | Accounting summary page |
| `/accounting/select-folder` | GET | - | Folder selector |
| `/accounting/refresh` | GET | - | Refresh accounting data |
| `/accounting/use-ssh` | GET | - | Switch to SSH mode |
| `/accounting/use-local` | GET | - | Switch to local mode |
| `/accounting/download/<kind>` | GET | - | Download accounting data |
| `/api/accounting/ssh/status` | GET | - | SSH bridge status |

### Spamhaus Tool

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/spamhaus` | GET | - | Redirect alias |
| `/tools/spamhaus/` | GET | - | Spamhaus workbench |
| `/tools/spamhaus/api/start` | POST | - | Start scan |
| `/tools/spamhaus/api/job/<id>` | GET | - | Job status |
| `/tools/spamhaus/api/poll-infra` | POST | - | Poll infrastructure |
| `/tools/spamhaus/api/cache-results` | GET | - | Cache results |
| `/tools/spamhaus/api/export/<id>` | GET | - | Export results |

### Extractor Tool

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/extractor` | GET | - | Redirect alias |
| `/tools/extractor/` | GET | - | Extractor workbench |
| `/tools/extractor/api/settings` | GET/POST | - | Get/save settings |
| `/tools/extractor/api/extraction-runs` | GET/POST | - | List/create runs |
| `/tools/extractor/api/extraction-runs/<id>` | GET | - | Run detail |

### Infrastructure Tool

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/infra` | GET | - | Redirect alias |
| `/tools/infra/` | GET | - | Infrastructure workbench |
| `/tools/infra/api/data` | GET/POST | - | Get/update infrastructure data |
| `/tools/infra/api/dkim/check-ssh` | POST | - | Check DKIM via SSH |
| `/tools/infra/api/dkim/generate` | POST | - | Generate DKIM keys |
| `/tools/infra/api/pmta/poll-config` | POST | - | Poll PMTA configuration |
| `/tools/infra/api/namecheap/test` | POST | - | Test Namecheap API |
| `/tools/infra/api/namecheap/poll-domain` | POST | - | Poll domain DNS |
| `/tools/infra/api/namecheap/verify-domain` | POST | - | Verify domain DNS |
| `/tools/infra/api/spamhaus-queue` | GET | - | Spamhaus queue |
| `/tools/infra/api/spamhaus-queue/import` | POST | - | Import from queue |

### Tracker Tool

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/tracker` | GET | - | Redirect alias |
| `/tools/tracker/` | GET | - | Tracker workbench |
| `/tools/tracker/generate` | POST | - | Generate tracking links |
| `/tools/tracker/stay` | GET/POST | - | Stay-alive endpoint |
| `/tools/tracker/stay/analyze` | POST | - | Analyze stay metrics |

---

## Data Structures

### Campaign Record

```python
{
    "id": str,
    "name": str,
    "created_at": str,       # ISO 8601
    "updated_at": str,       # ISO 8601
    "jobs": int,
    "status": str,           # "draft", "running", "paused", "done", "error"
    "total_recipients": int,
    "start_clicks": int,
}
```

### Campaign Form State

```python
{
    "from_email": str,        # newline-separated
    "from_name": str,         # newline-separated
    "subject": str,           # newline-separated
    "body": str,
    "body_format": str,       # "html" or "text"
    "smtp_host": str,
    "smtp_port": int,
    "smtp_security": str,     # "starttls", "ssl", "none"
    "smtp_user": str,
    "smtp_timeout": int,
    "ssh_host": str,
    "ssh_port": int,
    "ssh_user": str,
    "ssh_key_path": str,
    "ssh_timeout": int,
    "delay_s": float,
    "chunk_size": int,
    "thread_workers": int,
    "max_rcpt": int,
    "domain_plan": dict,      # domain -> recipient count
}
```

### Job Record

```python
{
    "id": str,
    "campaign_id": str,
    "status": str,            # "running", "done", "paused", "backoff", "error", "stopped"
    "bridge_mode": str,       # "counts" or "legacy"
    "created_at": str,
    "updated_at": str,
    "sent": int,
    "failed": int,
    "delivered": int,
    "deferred": int,
    "complained": int,
    "queued": int,
    "progress": int,          # 0-100
}
```

### Job Detail API Response

The `/api/job/<id>` response includes extended fields:

- `totals` - sent/failed/skipped/invalid counts
- `domain_state` - per-domain planned/sent/failed
- `chunk_states` - chunk lifecycle data
- `outcome_series` - time-series for trend charts
- `pmta_live` - live PMTA telemetry (spool, queue, connections, traffic)
- `pmta_diag` - PMTA diagnostics
- `pmta_pressure` - pressure score and signal
- `bridge_state` - SSH bridge connection status
- `logs` - runtime event log

---

## Key Helper Functions

### Campaign Management
- `get_campaign(id)` / `get_or_create_campaign(id)` - Campaign CRUD
- `load_campaigns()` / `save_campaigns()` - JSON persistence
- `load_campaign_forms()` / `save_campaign_forms()` - Form state persistence

### Job Management
- `get_job(id)` / `build_job_detail(id)` - Job data access
- `_advance_job_runtime(job)` - Simulated runtime progress
- `_append_job_event(job, event, message, level)` - Event logging

### PMTA Integration
- `load_pmta_monitor_snapshot(job)` - SSH-based PMTA live telemetry
- `resolve_pmta_runtime_for_job(job)` - SSH config resolution chain
- `build_accounting_summary()` - Aggregate PMTA accounting stats
- `load_pmta_records()` / `load_pmta_commands()` - Data loading

### DNS & Domain Auth
- `_build_domain_dns_row(domain, selector, expected_auth)` - Full DNS audit row
- `_check_domain_auth_records(domain, selector, expected_auth)` - SPF/DKIM/DMARC check
- `_estimate_message_spam_score(subject, body, format)` - Heuristic spam scoring (0-10)

### Rendering
- `inject_nibiru_navbar(html, active_page)` - Injects top navigation
- `render_tool_page(html, active_page)` - Wraps response with navbar
- `render(page, title, body, page_script)` - Full page template rendering

---

## Storage

### Files
- `database/campaigns.json` - Campaign list
- `database/campaign_forms.json` - Campaign form states per campaign

### In-Memory
- `JOBS` - Job list (initialized with demo data)
- `DASHBOARD_DATA` - Dashboard state with KPIs and demo values
- `CAMPAIGNS_STATE` - Loaded campaigns
- `CAMPAIGN_FORMS_STATE` - Loaded form states

---

## Entry Point

```python
app = Flask(__name__)
app.secret_key = os.getenv("NIBIRU_SECRET_KEY", "nibiru-dev-secret")
```

Imports and integrates: `script1`, `script2`, `script3`, `script4`, `script5`, `script6`, `tools.dns_shaker.DNSShaker`.
