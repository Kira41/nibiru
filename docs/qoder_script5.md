# script5.py - Email Open Tracking & Stay Monitoring

## Overview

`script5.py` is the email open tracking tool. It generates unique tracking images per recipient, packages them into a deployable ZIP, and later analyzes server-side access logs to determine which emails were opened.

**File size:** ~39KB
**Role:** Open-tracking resolution engine and engagement analytics input source.

---

## Dependencies

- **Flask** - Web framework
- **Pillow (PIL)** - 1x1 PNG image generation
- **nibiru** - `database_path`

---

## Flask Routes

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/` | GET | `index()` | Packager dashboard with email input form |
| `/generate` | POST | `generate()` | Parse emails, generate identifiers, create ZIP package |
| `/stay` | GET/POST | `stay_dashboard()` | GET: empty stay monitor form; POST: analyze logs from URLs |
| `/stay/analyze` | POST | `stay_analyze_api()` | API endpoint for JS polling - returns analysis JSON |

---

## Global Configuration

| Variable | Value | Purpose |
|----------|-------|---------|
| `DB_PATH` | `database/tracker.db` | SQLite database path |
| `IPDETECTIVE_API_URL` | `https://api.ipdetective.io/ip` | Bot IP detection API |
| `IPDETECTIVE_API_KEY` | From env or hardcoded default | API key for IPDetective |
| `BOT_IP_CACHE` | `Dict[str, bool]` | In-memory cache for bot IP lookups |
| `PAGE_SIZE` | 50 | Records per page |

---

## Database Schema

### Table: `email_mappings`

| Column | Type | Purpose |
|--------|------|---------|
| `email` | TEXT PRIMARY KEY | Email address |
| `identifier` | TEXT NOT NULL | 10-digit tracking identifier |
| `created_at` | TEXT NOT NULL | ISO timestamp of first creation |
| `last_generated_at` | TEXT NOT NULL | ISO timestamp of last generation |

---

## Identifier Generation

### `email_to_10_digits(email)`

Deterministic mapping from email to 10-digit numeric identifier:

```
email -> normalize (strip, lowercase)
      -> SHA-256 hash
      -> take first 8 bytes
      -> interpret as big-endian integer
      -> modulo 10,000,000,000
      -> zero-pad to 10 digits
```

This function is shared with `script4.py` to ensure tracking image URLs in sent emails match the identifiers in the tracking system.

---

## ZIP Package Generation

### `build_zip(emails)`

Creates a deployable archive for the tracking server.

**ZIP structure:**

```
email_image_bundle.zip
├── track.php          (644) - Server-side logging script
├── .htaccess          (644) - Apache rewrite rules
└── image/             (755) - Image directory
    ├── 0123456789.png (644) - 1x1 white PNG per email
    ├── 9876543210.png (644)
    └── ...
```

### track.php

PHP script that:
- Detects client IP (CF-Connecting-IP, X-Forwarded-For, X-Real-IP, REMOTE_ADDR)
- Validates filename: regex `^[A-Za-z0-9._-]+\.png$`
- Path traversal protection via `realpath()`
- Logs access to `image_log.jsonl` in JSONL format
- Sets cache-control headers to prevent caching

### .htaccess

Apache configuration:
- URL rewriting for clean image URLs
- Directory listing disabled
- No-index configuration

---

## Tracking Workflow

1. **Prepare** - User enters recipient emails
2. **Generate** - `POST /generate` validates emails, generates identifiers, stores in DB, creates ZIP
3. **Deploy** - User manually uploads ZIP to campaign/tracking server
4. **Send** - Mailer (script4) embeds `{src_root}/{identifier}.png` in email body
5. **Track** - When email is opened, image requested from tracking server, logged to `image_log.jsonl`
6. **Analyze** - Stay monitor fetches JSONL logs, matches identifiers back to emails

---

## Stay/Open Analysis

### `analyze_stay_data(raw_urls, known_event_keys=None)`

Fetches and analyzes remote JSONL access logs.

**Process:**

1. **URL normalization** - Ensures URLs end with `/image_log.jsonl`
2. **JSONL fetching** - HTTP GET for each URL
3. **Identifier extraction** - Regex `(\d{10})\.png` on image/request_uri fields
4. **Bot filtering** - IPDetective API checks each IP; results cached
5. **Event deduplication** - Unique event_key: `{url}|{timestamp}|{image}|{ip}`
6. **Email matching** - Identifier -> email lookup from database
7. **Domain analysis** - Count matches per email domain, sorted by frequency

**Return structure:**

```python
{
    "urls": list,                  # Analyzed URLs
    "matches": list,               # Matched records (identifier -> email)
    "matches_page": dict,          # Paginated matches
    "new_matches": list,           # Previously unseen matches
    "all_rows": list,              # All extracted records
    "matched_count": int,
    "new_matched_count": int,
    "found_count": int,
    "stored_email_count": int,
    "url_count": int,
    "unmatched_ids": list,         # IDs found in logs but not in database
    "errors": list,                # URL fetch errors
    "stored_mappings": list,       # All email mappings
    "stored_mappings_page": dict,  # Paginated mappings
    "domain_stats": list,          # Per-domain open counts
    "domain_stats_page": dict,     # Paginated domain stats
    "run_at": str,                 # ISO timestamp
}
```

---

## Bot Detection

### `is_bot_ip(ip_value)`

Queries IPDetective API to determine if an IP is a known bot/crawler.

- Results cached in `BOT_IP_CACHE` dictionary
- API key configurable via `IPDETECTIVE_API_KEY` env var
- Used to filter false positives from open tracking (bots requesting images)

---

## Frontend Features

- Two-tab interface: Packager and Stay Monitor
- Email input with validation and deduplication
- ZIP download on generation
- Stay monitor with URL input for JSONL log sources
- Auto-polling every 30 seconds for live monitoring
- Paginated results (50 per page)
- Domain statistics with top domain highlight
- Matched/unmatched identifier tracking
- New match highlighting (events not previously seen)

---

## Key Helper Functions

| Function | Purpose |
|----------|---------|
| `parse_emails(raw)` | Validate and normalize email list |
| `parse_urls(raw)` | Validate and normalize URL list |
| `extract_identifier_from_text(value)` | Extract 10-digit ID from text |
| `normalize_jsonl_url(url)` | Ensure URL ends with `/image_log.jsonl` |
| `fetch_records_from_jsonl(url)` | HTTP fetch and parse JSONL records |
| `extract_domain_from_record(record)` | Get domain from referer/source fields |
| `paginate_items(items, page, page_size)` | Paginate result lists |
| `make_blank_png_bytes(w, h)` | Generate 1x1 white PNG via PIL |
| `build_php_file()` | Generate track.php source code |
| `build_htaccess()` | Generate .htaccess rules |
