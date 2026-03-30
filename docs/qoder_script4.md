# script4.py - SMTP Sending Orchestration (Shiva)

## Overview

`script4.py` is the sending orchestration module called "Shiva". It provides the send page template and an SMTP sending worker for email delivery. It is not a standalone Flask app but a helper module imported by `nibiru.py`.

**File size:** ~74KB
**Role:** Campaign sending orchestrator and execution control surface.

---

## Dependencies

- **Flask** - `render_template_string`
- **smtplib** / **ssl** - SMTP connections
- **hashlib** - SHA-256 for identifier generation
- **threading** - Delay between messages

---

## Module Exports

### `render_send_page(campaign_ts, campaign_id, campaign_name_suffix="")`

Returns a tuple `(body_html, script_tag)` for rendering the send page. Called by `nibiru.py` when mounting the `/send` route.

---

## Helper Functions

| Function | Purpose |
|----------|---------|
| `split_multivalue_field(value)` | Splits input by newlines, commas, or semicolons |
| `pick_first_nonempty_line(value)` | Returns first non-empty item from multivalue field |
| `is_valid_email(candidate)` | Basic email validation (has @, domain has dot) |
| `email_to_10_digits(email)` | SHA-256 hash -> first 8 bytes -> mod 10B -> zero-padded 10 digits |

---

## SMTP Send Worker

### `smtp_send_worker(job_id, payload, *, get_job, append_job_event, safe_int, iso_fn)`

Background worker function designed to run in a separate thread. Accepts injected callbacks for job state access and event logging.

### Configuration (from payload)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `smtp_host` | str | required | SMTP server hostname |
| `smtp_port` | int | 25 | SMTP port |
| `smtp_security` | str | "none" | `ssl`, `starttls`, or `none` |
| `smtp_timeout` | int | min 5 | Connection timeout |
| `smtp_user` | str | optional | SMTP username |
| `smtp_pass` | str | optional | SMTP password |
| `from_name` | str | optional | Sender display name |
| `from_email` | str | required | Sender email address |
| `subject` | str | required | Email subject line |
| `body` | str | required | Email body content |
| `body_format` | str | "text" | `html` or `text` |
| `urls_list` | str | optional | Newline-separated URLs for [URL] macro |
| `src_list` | str | optional | Source URLs for [SRC] macro |
| `reply_to` | str | optional | Reply-To header |
| `delay_s` | float | 0 | Delay between messages (seconds) |

### Connection Logic

1. `smtp_security == "ssl"` -> `smtplib.SMTP_SSL()` with SSL context
2. Otherwise -> `smtplib.SMTP()` with `ehlo()`
3. `smtp_security == "starttls"` -> `starttls()` then `ehlo()`
4. If `smtp_user` provided -> `login(user, pass)`

### Email Construction

- Uses `email.message.EmailMessage`
- Headers: Subject, From (name + email or email only), To, Reply-To
- Body format: HTML (with text fallback) or plain text
- Macro replacement applied before sending

### Message Macros

| Macro | Replacement |
|-------|-------------|
| `[URL]` | Random pick from urls_list |
| `[SRC]` | `{src_root}/{email_to_10_digits(recipient)}.png` |

### Pause/Stop Support

On each recipient iteration, the worker checks `job.status`:
- If `paused` or `stopped` -> breaks out of loop
- Allows external control via job state mutation

### Completion

- Success: `status = "done"`, `phase = "completed"`, `progress = 100`
- Error: `status = "error"`, `phase = "error"`
- Always: SMTP connection closed in `finally` block

---

## Send Page Template

### Layout Structure

```
SHIVA - {campaign_name}
├── Manual Send Toggle
├── Form (action="/start")
│   ├── Hidden inputs (campaign_id, infra_payload, manual_send_mode, banished_ips, banished_domains)
│   ├── Infrastructure Card (auto mode only)
│   ├── SMTP Settings Card (manual mode only)
│   │   ├── Host, Port, Security, Timeout
│   │   ├── Username, Password (with remember checkbox)
│   │   └── Test SMTP button
│   ├── SSH Connection Card (manual mode only)
│   │   ├── Host, Port, Username, Key Path, Password, Timeout
│   │   └── Test SSH button
│   ├── Preflight & Send Controls
│   │   ├── Spam score display
│   │   ├── Blacklist status
│   │   ├── Domain verification table
│   │   ├── Preflight Check button
│   │   ├── Delay, Max Recipients, Chunk Size, Thread Workers, Sleep Between Chunks
│   │   ├── Force-use blacklisted IPs/domains checkboxes
│   │   └── AI Rewrite section (OpenRouter token)
│   └── Message Card
│       ├── Sender Name, Sender Email (manual mode)
│       ├── Subject, Format, Reply-To
│       ├── Spam score limit (slider 1-10)
│       ├── Domain score limit (slider -10 to 20)
│       ├── Body, URL list, SRC list
│       ├── Recipients (textarea + file upload)
│       ├── Maillist Safe whitelist
│       └── Start Sending button
└── In Use Domains Card
    ├── Domain search
    └── Domain verification table
```

---

## Manual vs Automated Mode

### Manual Mode (ON)

- SMTP Settings Card visible - user fills all fields
- SSH Connection Card visible
- Sender Name/Email fields visible
- Preflight Button visible
- Infrastructure Card hidden
- Form field `manual_send_mode = "1"`

### Automated Mode (via Infrastructure Bridge)

- Infrastructure Card shows bridge summary from script3
- SMTP/SSH fields auto-populated from first server in payload
- Sender emails/names merged from all servers
- Manual fields hidden
- Form field `manual_send_mode = "0"`
- Triggered by localStorage marker `shivaBridgeLaunchV1` (2-minute expiry)

---

## Client-Side API Calls

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/campaign/{id}/form` | GET/POST | Load/save form state |
| `/api/campaign/{id}/clear` | POST | Clear campaign data |
| `/api/campaign/{id}/domains_stats` | GET | Get domain statistics |
| `/api/smtp_test` | POST | Test SMTP connection |
| `/api/ssh_test` | POST | Test SSH connection |
| `/api/preflight` | POST | Run preflight checks |
| `/api/ai_rewrite` | POST | AI-assisted content rewriting |
| `/start` | POST | Start sending campaign |

---

## Preflight Check

Evaluates before sending:
- Spam score estimation (heuristic 0-10)
- DNSBL listings (Spamhaus) per sender IP
- DBL listings per sender domain
- SPF/DKIM/DMARC authentication status
- Domain reputation scores

Produces `bannedIps` and `bannedDomains` lists for send-time exclusion.

---

## Form Persistence

- Auto-saves on every control change (debounced 250ms)
- Saved to SQLite via `/api/campaign/{id}/form`
- Passwords only saved if "Remember password" checked
- Restored on page load from database
