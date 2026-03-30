# PMTA Live Monitoring Audit (Jobs path)

Date: 2026-03-28

This document maps how PMTA live telemetry is currently wired in `nibiru.py` + `script6.py`, why Jobs shows weak/empty state, and what to change.

## Current flow (as implemented)

1. `/jobs` renders job cards from `JOBS` and refreshes each card by calling `/api/job/<job_id>`.
2. `/api/job/<job_id>` calls `build_job_detail(job_id)`.
3. `build_job_detail()` calls `load_pmta_monitor_snapshot(job)` and injects `pmta_live`, `pmta_diag`, and `pmta_outcomes` into response JSON.
4. `load_pmta_monitor_snapshot(job)`:
   - Builds fallback values from the job counters.
   - Builds runtime SSH config using `script6.build_runtime_config(DASHBOARD_DATA["message_form"])`.
   - If SSH disabled, returns fallback immediately.
   - If SSH enabled, runs three remote CLI commands through `script6.run_ssh_command(...)`:
     - `pmta show status`
     - `pmta show topqueues`
     - `pmta show queues --mode=backoff`
   - Parses text output with regex and fills live/diag objects.
5. Frontend JS in Jobs renders PMTA panel from `j.pmta_live` and diagnostics from `j.pmta_diag`.

## Data sources currently used by Jobs PMTA live

### SSH
- Source is PMTA CLI over SSH, via `script6.run_ssh_command` and commands above.
- Commands are global PMTA status commands; they are not scoped by current campaign/job.

### Local files
- Jobs PMTA panel does not read local PMTA accounting files directly.
- Local-vs-SSH accounting mode in `script6.py` is used by the Accounting page, not Jobs PMTA panel.

### Fallback/demo
- If SSH is not enabled, or parsing fails, Jobs still gets synthetic fallback values from the job row (`queued`, `deferred`, `sent`) and zero/defaults for connections.
- `JOBS` itself is initialized with demo data rows.
- Default dashboard `message_form` also contains demo SSH host/user.

## Send-page SSH config reachability

- Send page persists form state per campaign in `CAMPAIGN_FORMS_STATE` using `/api/campaign/<id>/form`.
- But Jobs PMTA monitor builds SSH runtime config from static `DASHBOARD_DATA["message_form"]` instead of the campaign form snapshot or job snapshot.
- `/start` does not store SSH fields into `send_snapshot`; it only stores limited SMTP/send fields.

Result: SSH settings entered on Send generally do **not** reach Jobs PMTA monitor functions.

## Job-awareness vs global behavior

Current PMTA monitoring is mostly global:
- PMTA commands are global status/topqueues/backoff views.
- No command includes campaign/job identifiers.
- No filtering by job sender, campaign tag, queue ownership, x-job headers, or accounting `job_id`.

Only fallback numbers are job-derived (from in-memory job counters).

## Are script6 runtime/SSH helpers invoked by Jobs?

Yes:
- `script6.build_runtime_config(...)` is called in `load_pmta_monitor_snapshot`.
- `script6.run_ssh_command(...)` is called for each PMTA command attempt.

But these are invoked with the wrong config source (`DASHBOARD_DATA.message_form`), so they are disconnected from Send campaign settings.

## Failure behavior (missing/wrong/disconnected SSH)

- Missing host/user (`ssh_enabled = False`): immediate fallback with `pmta_live.ok=False`, reason `SSH not configured`.
- Password provided: `run_ssh_command` raises unsupported-password error (script6 requires key/agent here).
- Bad host/key/network/command exit: error captured per command; if no status output, panel remains `ok=False` and diagnostic error text is set.
- Because fallback values are still populated, UI can show non-empty but non-live numbers from job counters.

## Why Jobs shows no meaningful PMTA live state (root causes)

1. **Config disconnect:** Jobs monitor uses static dashboard config, not Send campaign SSH settings.
2. **No job linkage:** PMTA live queries are global PMTA snapshots, not campaign/job-scoped telemetry.
3. **No accounting join:** Jobs panel doesn’t consume `script6` accounting analysis pipeline for per-job outcomes/tails.
4. **Weak parser coverage:** Text regex parsing relies on specific CLI output shapes; mismatches keep many fields default/empty.
5. **Silent fallback masking:** Fallback values make panel look populated while still not truly live.
6. **In-memory demo model:** primary `JOBS` dataset is demo/in-memory and not tied to real PMTA IDs/headers.

## Precise edit plan to make PMTA live real + job-aware

1. **Single source of PMTA runtime config (campaign-aware)**
   - Add resolver `resolve_pmta_runtime_for_job(job)` that checks, in order:
     1) `job.send_snapshot.ssh_*`
     2) `CAMPAIGN_FORMS_STATE[job.campaign_id].ssh_*`
     3) env vars
   - Stop using `DASHBOARD_DATA["message_form"]` for Jobs runtime.

2. **Persist SSH with job at start**
   - Extend `/start` `send_snapshot` to include `ssh_host`, `ssh_port`, `ssh_user`, `ssh_key_path`, `ssh_timeout`.
   - Optionally store `pmta_accounting_file` and non-secret SSH auth mode metadata.

3. **Introduce job-scoped PMTA/accounting provider**
   - Add `collect_pmta_live_for_job(job, runtime_config)` returning:
     - global PMTA status,
     - job-scoped accounting counters (match by accounting `job_id` / campaign tag / sender/domain).
   - Prefer accounting-derived outcomes for delivered/bounced/deferred by job.

4. **Wire script6 accounting path into Jobs (read-only service layer)**
   - Reuse parse helpers (`parse_csv_text`) on remote accounting tail via SSH.
   - Add fast query mode: `tail -n N acct.csv` over SSH then filter rows by job identity markers.

5. **Clear fallback semantics in API**
   - Add `pmta_live.source = live|fallback` and `pmta_live.reason` strictly when fallback.
   - Expose `bridge_state.last_error_code` categories (missing_config/auth/network/parse).

6. **Strengthen parser robustness**
   - Parse `pmta --xml show status` when available, fallback to plain text parser.
   - Normalize queue/topqueue parsing and preserve parse diagnostics.

7. **Observability + tests**
   - Unit tests for runtime-config resolution precedence.
   - Unit tests for missing/wrong SSH behavior and fallback flags.
   - Parser fixtures for representative PMTA status outputs.
   - API contract test for `/api/job/<id>` returning job-scoped source labels.

