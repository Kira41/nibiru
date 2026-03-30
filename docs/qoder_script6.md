# script6.py - PowerMTA Accounting Analytics Dashboard

## Overview

`script6.py` analyzes PowerMTA accounting CSV files from one or more sending servers. It supports both local folder-based analysis and remote SSH-based retrieval. Provides delivery metrics, bounce classification, domain analysis, infrastructure diagnostics, and actionable insights.

**File size:** ~82KB
**Role:** Post-send accounting analytics and diagnostics dashboard.

---

## Dependencies

- **Flask** - Web framework
- **paramiko** - SSH connections (password-based fallback)
- **nibiru** - `database_path`
- **tkinter** - File dialog for folder selection

---

## Flask Routes

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/` | GET | `index()` | Renders analytics dashboard |
| `/select-folder` | GET | `select_folder()` | Opens file dialog for local CSV folder |
| `/refresh` | GET | `refresh()` | Refreshes analysis from current source |
| `/use-ssh` | GET | `use_ssh()` | Switches to SSH source mode |
| `/use-local` | GET | `use_local()` | Switches to local folder mode |
| `/api/stats` | GET | `api_stats()` | Returns JSON summary stats |
| `/download/<kind>` | GET | `download()` | Downloads CSV/TXT reports |

---

## Global Configuration

| Variable | Value | Purpose |
|----------|-------|---------|
| `CACHE_DB` | `database/campaign_monitor_cache.db` | SQLite cache database |
| `MAX_WORKERS` | `max(4, cpu_count)` | Thread pool size for parallel CSV parsing |
| `PMTA_ACCOUNTING_FILE` | `/var/log/pmta/acct.csv` | Default remote accounting file path |
| `DEFAULT_SOURCE_MODE` | `"local"` | Default data source mode |

---

## Database Schema

### Table: `folder_cache`

| Column | Type | Purpose |
|--------|------|---------|
| `folder_path` | TEXT PRIMARY KEY | Folder path identifier |
| `signature` | TEXT NOT NULL | File names + sizes + mtimes hash |
| `payload` | TEXT NOT NULL | Full analysis JSON |
| `updated_at` | TEXT NOT NULL | ISO timestamp |

### Table: `recipient_domain_cache`

| Column | Type | Purpose |
|--------|------|---------|
| `folder_path` | TEXT NOT NULL | Folder path |
| `signature` | TEXT NOT NULL | Signature for cache validity |
| `row_rank` | INTEGER NOT NULL | 1-indexed rank (for pagination) |
| `domain` | TEXT | Recipient domain |
| `total` | INTEGER | Total records |
| `delivered` | INTEGER | Delivered count |
| `bounced` | INTEGER | Bounced count |
| `unknown` | INTEGER | Unknown count |
| `delivery_rate` | REAL | Delivery percentage |
| `bounce_rate` | REAL | Bounce percentage |
| `top_bounce_reason` | TEXT | Most frequent bounce reason |
| `top_bounce_category` | TEXT | Most frequent bounce category |
| `top_mx_host` | TEXT | Most frequent MX host |
| `recommendation` | TEXT | Recommended action |
| `mode` | TEXT | "delivered", "bounced", or "mixed" |
| `risk_level` | TEXT | "high" or "normal" |

**Primary key:** `(folder_path, signature, row_rank)`

---

## PMTA Accounting CSV Parsing

### Column Mapping (Index -> Field)

| Index | Field | Description |
|-------|-------|-------------|
| 0 | `type_code` | D=delivered, B=bounced |
| 1 | `log_time` | Log timestamp |
| 2 | `arrival_time` | Message arrival time |
| 3 | `sender` | Sender email |
| 4 | `recipient` | Recipient email |
| 6 | `result_word` | Status text (success, failed) |
| 7 | `smtp_status` | SMTP code (2.0.0, 5.5.1) |
| 8 | `response_text` | Full SMTP response |
| 9 | `mx_host` | Destination mail server |
| 10 | `dsn_group` | DSN category |
| 11 | `protocol` | SMTP version |
| 12 | `source_host` | Sending host |
| 14 | `source_ip` | Sending IP |
| 15 | `target_ip` | Receiving IP |
| 17 | `size` | Message size |
| 18 | `pool` | Sending pool name |
| 20 | `category_path` | Campaign category |

### Classification Logic

- **Delivered:** `type_code="d"` OR status contains "success"/"relayed" OR SMTP code starts "2.0.0"
- **Bounced:** `type_code="b"` OR status contains "fail" OR SMTP code starts "5"
- **Unknown:** Everything else

### Bounce Categories (8)

| Category | Description | Recommended Action |
|----------|-------------|-------------------|
| `blocklist` | IP/domain blocklisted | Review sender reputation |
| `spam-related` | Content/policy spam rejection | Review content |
| `bad-mailbox` | Non-existent recipient | Suppress permanently |
| `policy-rejection` | Receiver policy rejection | Check auth records |
| `temporary-or-remote-rejection` | Temporary failures | Retry later |
| `mailbox-full` | Full mailbox | Retry later |
| `timeout` | Connection timeout | Retry later |
| `other` / `unknown` | Unclassified | Investigate |

---

## Source Modes

### Local Mode

1. User selects folder via file dialog (Tkinter)
2. System scans for all `*.csv` files
3. Computes folder signature (file names + sizes + mtimes)
4. Checks SQLite cache; if signature matches, returns cached analysis
5. Otherwise: parses all CSVs in parallel (ThreadPoolExecutor)
6. Caches result in `folder_cache` table
7. Builds `recipient_domain_cache` for pagination

### SSH Mode

1. Builds runtime config from env vars or external config
2. Executes: `test -f {remote_file} && cat {remote_file}` via SSH
3. Parses CSV text from stdout
4. No caching (always fresh)
5. Source label: `ssh://{user}@{host}:{port}{path}`

---

## SSH Integration

### Dual Execution Paths

**Path 1: Subprocess SSH** (no password)
```
ssh -p {port} -o BatchMode=yes -o ConnectTimeout={timeout} -i {key} {user}@{host} {command}
```

**Path 2: Paramiko SSH** (password auth)
- Used when `ssh_pass` is set
- Disables key-based auth and agent
- Password authentication only

### Runtime Config Builder

`build_runtime_config(external_config=None)` resolves settings from:

1. External config dict (highest priority)
2. Environment variables (`PMTA_SSH_HOST`, `PMTA_SSH_USER`, `PMTA_SSH_PORT`, `PMTA_SSH_KEY_PATH`, `PMTA_SSH_PASS`, `PMTA_SSH_TIMEOUT`, `PMTA_ACCOUNTING_FILE`)
3. Hardcoded defaults (port=22, timeout=8, file=/var/log/pmta/acct.csv)

**Output:**
```python
{
    "ssh_host": str,
    "ssh_user": str,
    "ssh_port": str,
    "ssh_key_path": str,
    "ssh_pass": str,
    "ssh_timeout": int,
    "pmta_accounting_file": str,
    "ssh_enabled": bool,
}
```

---

## Analysis Engine

### `build_analysis(records, *, source_label, files_count, signature, bad_files, cacheable)`

Aggregates records into structured analytics:

1. **Partition** records by result (delivered/bounced/unknown)
2. **Aggregate by sender domain** - counts + bounce categories
3. **Aggregate by recipient domain** - counts + reasons + categories + MX hosts
4. **Build recipient domain rows** with delivery/bounce rates, risk levels, recommendations
5. **Build sender domain rows** - top 25 by volume
6. **Build infrastructure rows** - pools, source IPs, source hosts, MX hosts (top 6 each)
7. **Build bounce category rows** - counts with recommended actions
8. **Build timeline chart** - hourly buckets (last 36 hours)
9. **Generate 10 insights** - automated diagnostic text
10. **Build action lists** - retry_later + suppression_list

### Output Structure

```python
{
    "summary": {
        "total_rows": int,
        "delivered": int,
        "bounced": int,
        "unknown": int,
        "delivery_rate": float,
        "bounce_rate": float,
        "unique_sender_domains": int,
        "unique_recipient_domains": int,
        "pmta_runtime": dict,
    },
    "recipient_domain_rows": list,   # Ranked by volume
    "sender_domain_rows": list,      # Top 25
    "infra_rows": list,              # Pools, IPs, hosts, MX
    "bounce_category_rows": list,    # Categories with actions
    "recent_bounces": list,          # Top 80 most recent
    "insights": list,                # 10 auto-generated
    "chart_summary": dict,           # OK/Bounced/Unknown pie
    "bounce_chart": dict,            # Top 8 categories
    "timeline_chart": dict,          # 36 hourly buckets
    "retry_later": list,             # Temporary bounces
    "suppression_list": list,        # Permanent bad mailboxes
}
```

---

## Download Options

| Kind | Format | Content |
|------|--------|---------|
| `delivered_recipients` | CSV | Delivered recipient emails |
| `bounced_recipients` | CSV | Bounced recipients with reasons |
| `suppression_list` | TXT | Bad mailbox emails for suppression |
| `retry_list` | TXT | Temporary bounce emails for retry |
| `full_report` | CSV | All records with full detail |
| `insights` | TXT | Generated insights text |

---

## Key Helper Functions

| Function | Purpose |
|----------|---------|
| `percent(part, total)` | Safe percentage calculation |
| `normalize_email(value)` | Email normalization via `parseaddr()` |
| `extract_domain(email)` | Domain extraction from email |
| `bounce_category(reason, status)` | Classify bounce into 8 categories |
| `bounce_action(category)` | Recommended action per category |
| `classify_record(row)` | Classify as delivered/bounced/unknown |
| `parse_csv_file(path)` | Parse CSV with auto-dialect detection |
| `parse_csv_text(text, name)` | Parse CSV from string |
| `row_to_record(row, source)` | Normalize raw CSV row to record dict |
| `summarize_entity(records, key, top_n)` | Group and summarize by entity |
| `get_folder_signature(path)` | Compute folder content signature |
| `get_pmta_runtime_info()` | Probe PMTA status via SSH |

---

## Frontend Dashboard

- Summary KPI cards (total, delivered, bounced, rates)
- Recipient domain table (sortable, paginated 25-1000 rows)
- Sender domain table (top 25)
- Infrastructure diagnostics table
- Bounce category breakdown with actions
- Recent bounces list (80 most recent)
- Timeline chart (hourly delivery/bounce)
- Summary and bounce pie charts
- Insights panel (10 auto-generated)
- Action center (suppression + retry lists)
- PMTA runtime status display
- Source mode indicator (Local/SSH)
- Download buttons for all report types
