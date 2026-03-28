# Jobs page frontend/backend contract audit

Date: 2026-03-28 (UTC)
Scope inspected:
- `/jobs` rendering template and client JS
- `/api/jobs`
- `/api/job/<job_id>`
- `/api/accounting/ssh/status`
- `/api/dashboard` (checked because requested as possible dashboard/live API)
- all `fetch(...)` calls embedded in Jobs page JS

## API + fetch map (Jobs UI)

| UI callsite | Fetch URL | Exists in backend? | Backend function | Notes |
|---|---|---|---|---|
| card polling (`tickCard`) | `/api/job/${jobId}` | Yes | `api_job` -> `build_job_detail(job_id)` | Primary data source for every card update. |
| bridge status poll (`bridgeDebugTick`) | `/api/accounting/ssh/status` | Yes | `api_accounting_ssh_status` -> `load_pmta_monitor_snapshot(sample_job)` | Used only for bridge connection badge + bridge receiver text. |
| job action button (`controlJob`) | `/api/job/${jobId}/control` POST | **No** | Missing route | UI wired, backend absent (always fails). |
| job delete button (`deleteJob`) | `/api/job/${jobId}/delete` POST | **No** | Missing route | UI wired, backend absent (always fails). |

`/api/jobs` exists (`api_jobs` returns `{jobs: JOBS}`) but **is not fetched** by Jobs page JS; cards are server-rendered first and then individually polled via `/api/job/<id>`.

## Visible Jobs sections vs contract

Legend for status:
- ✅ fully wired and working
- 🟡 wired but empty because backend returns null/empty data
- 🟠 wired to fallback/demo data
- ❌ UI exists but backend source is missing

| UI section (visible card area) | JS/API source | Backend source | Fields expected by UI | Fields currently present from backend/runtime | Current runtime status | Problem |
|---|---|---|---|---|---|---|
| Header pills (Status/epm/ETA) | `updateCard()` from `/api/job/<id>` | `build_job_detail()` | `status`, `speed_epm`, `eta_s` | `status` present; `speed_epm`/`eta_s` missing -> defaults to `0`/`ETA —` | 🟡 | speed + ETA contract not produced by backend. |
| Triage badges (mode/freshness/health/risk/bridge/integrity) | `renderTriageBadges()` + `/api/job/<id>` and `/api/accounting/ssh/status` | `build_job_detail()`, `api_accounting_ssh_status()` | `bridge_mode`, freshness timestamps, health/error counters, integrity counters, bridge state | `bridge_mode` + ts present; most health/integrity counters absent so 0/— fallbacks; bridge status comes from ssh endpoint | 🟠 | mostly synthetic/fallback; integrity/health detail payload sparse. |
| KPI counters (Sent/Pending/Del/Bnc/Def/Cmp) + rates | `updateCard()` `/api/job/<id>` | `build_job_detail()` from JOBS + PMTA outcomes fallback | `total,sent,failed,skipped,invalid,delivered,bounced,deferred,complained` | all present (skipped/invalid hardcoded 0), pending computed client-side | ✅ | counts work but some fields are hardcoded (not real pipeline counters). |
| PMTA Live Panel grid | `updateCard()` -> `_renderPmtaPanel(j.pmta_live)` | `load_pmta_monitor_snapshot()` | `pmta_live.enabled/ok/reason/...queue/spool/connections/traffic/top_queues/ts` | present; if SSH not configured returns fallback with `ok:false` + synthetic queue/traffic values | 🟠 | often monitor-unreachable/fallback because ssh config absent. |
| PMTA diagnostics strip + error summary | `pmta_diag`, `pmtaErrorSummary`, `renderErrorTypes()` | `load_pmta_monitor_snapshot()` + `build_job_detail()` | `pmta_diag.*`, `accounting_error_counts`, `accounting_last_errors` | `pmta_diag` present (fallback), accounting error arrays not returned -> summary mostly inferred from aggregate counts | 🟡 | no per-recipient accounting errors in payload; diagnostics shallow. |
| Progress bars (send/chunks/domains) | `updateCard()` from `/api/job/<id>` | `build_job_detail()` | `total/sent/failed/skipped`, chunk counters, `domain_plan/domain_sent/domain_failed` | total/sent/failed/skipped present; **domain_* and chunk lifecycle fields absent** -> chunks/domains bars show 0/empty | 🟡 | backend does not emit required domain + chunk progress model. |
| Quick issues banner | computed in JS | `/api/job/<id>` | `status`, `chunks_abandoned`, `chunk_states`, spam threshold | only `status` reliably present; others mostly absent | 🟡 | alerts under-report due to missing fields. |
| Current chunk panel | `getLiveChunks()`, `chunkLine`, `chunkDomains` | `/api/job/<id>` | `active_chunks_info` or `chunk_states` or `current_chunk_info` + domain maps | backend returns only coarse `chunks` array, not expected live structures | ❌ | UI exists, data contract mismatch (wrong field names/shape). |
| Backoff panel | `backoffLine` from live chunk/history arrays | `/api/job/<id>` | `chunk_states[]` with status/next_retry/reason/attempt | missing `chunk_states` | ❌ | cannot show real backoff telemetry. |
| Outcomes (PMTA accounting) + trend | `outcomes`, `outcomeTrend` | `/api/job/<id>` + `pmta_live` | aggregate outcomes + `accounting_last_ts` + `outcome_series[]` | aggregate counts present; `outcome_series` missing -> trend stays `—`; timestamp present | 🟡 | trend/history absent. |
| Top providers / top domains | `renderTopDomains()` | `/api/job/<id>` | `domain_plan`, `domain_sent`, `domain_failed`, optional `pmta_domains` | `pmta_domains` present (derived), but `domain_plan/sent/failed` absent -> mostly empty/default provider bars | 🟡 | provider/domain progress not truly wired. |
| System/Provider/Integrity blocks | `renderIssueBlocks()` | `/api/job/<id>` | bridge/internal/provider/integrity breakdown fields + sample arrays | most optional fields missing; delivered/bounced etc present | 🟡 | blocks render but largely placeholder `—`/0. |
| Legacy quality + errors | `counters`, `errorTypes`, `lastErrors*`, `internalErrors` | `/api/job/<id>` | safe-list counters + accounting/internal error collections | counters mostly default 0 from missing fields; no detailed error arrays | 🟡 | diagnostics are mostly synthetic fallback text. |
| Bridge snapshot receiver box | `renderBridgeReceiver()` + `/api/accounting/ssh/status` | `/api/job/<id>` + ssh status API | bridge success/accounting timestamps, cursor fields (legacy mode) | counts-mode timestamps present; legacy cursor stats missing | 🟡 | partial wiring only. |
| Chunk preflight tables (live/history) | `renderChunkLive()` + `renderChunkHist()` | `/api/job/<id>` | `active_chunks_info`/`chunk_states` rich rows | not provided | ❌ | tables stay “No active chunk / No chunk states yet”. |
| Logs section | none (no visible logs widget in Jobs HTML) | backend returns `logs` array from `build_job_detail()` | if section existed, `logs[]` | `logs[]` exists in API but not rendered | ❌ | backend has logs, UI has no logs panel binding. |
| Job action buttons (Pause/Resume/Stop/Delete) | `controlJob/deleteJob` fetch calls | missing control/delete API routes | `/api/job/<id>/control`, `/api/job/<id>/delete` | routes absent | ❌ | buttons fail at runtime. |

## Fields rendered in requested categories

### Status
Rendered from: `status`, `bridge_mode`, bridge connection state, freshness timestamps, risk (computed from outcomes), integrity counters.

Missing/partial at runtime:
- `bridge_failure_count`, `internal_health_failures`, `bridge_last_error_message` mostly absent.

### Progress
Rendered from: `total,sent,failed,skipped`, `chunk_* counters`, `domain_plan/domain_sent/domain_failed`.

Missing/partial at runtime:
- `chunk_unique_done`, `chunk_unique_total`, `chunks_backoff`, `chunks_abandoned`, `chunk_attempts_total`
- `domain_plan`, `domain_sent`, `domain_failed`

### PMTA
Rendered from: `pmta_live`, `pmta_diag`, `pmta_pressure`, `monitor_commands_used` (indirect), bridge status endpoint.

Runtime reality:
- Structure exists, but often fallback/`ok:false` unless SSH config exists.

### Outcomes
Rendered from: `delivered,bounced,deferred,complained,sent`, `accounting_last_ts`, `outcome_series`.

Missing:
- `outcome_series` not returned -> no sparkline trend.

### Providers
Rendered from: `domain_plan` + domain counters, `provider_breakdown`, `provider_reason_buckets`, `accounting_last_errors`.

Missing:
- most provider breakdown arrays/maps absent.

### Integrity
Rendered from: `duplicates_dropped,job_not_found,missing_fields,db_write_failures`, `integrity_last_samples`.

Missing:
- sample arrays and non-zero counters usually absent.

### Chunk history
Rendered from: `active_chunks_info`, `chunk_states`, `current_chunk_info`, lane/chunk metadata.

Missing:
- API currently returns only `chunks` (different schema), so both tables are mostly empty.

### Logs
- API returns `logs` array.
- Jobs HTML/JS has no visible logs panel wired to `logs`.

## Highest-priority mismatches (top 5)

1. **Missing control/delete backend routes** for existing UI buttons (`/api/job/<id>/control`, `/api/job/<id>/delete`).
2. **Chunk telemetry schema mismatch** (`chunk_states`/`active_chunks_info` expected; backend returns `chunks` only).
3. **Domain/provider progress schema missing** (`domain_plan/domain_sent/domain_failed` absent), breaking provider/domain progress visuals.
4. **Outcomes trend missing** (`outcome_series` absent), so trend panel is permanently placeholder.
5. **Bridge/internal/provider/integrity detail payload mostly absent**, leaving major diagnostic blocks in fallback/empty state.

## Smallest patch set to make Jobs page operational

1. **Add two lightweight API routes**:
   - `POST /api/job/<job_id>/control` to mutate `status/paused/stop_requested` in `JOBS`.
   - `POST /api/job/<job_id>/delete` to remove the job.
2. **Normalize `/api/job/<job_id>` response contract** by adding minimally required fields (can be synthesized):
   - `chunk_states` from existing `chunks` (map shape).
   - `current_chunk_info` from latest running/backoff chunk.
   - `domain_plan`, `domain_sent`, `domain_failed` from `domain_state`.
3. **Emit `outcome_series`** with at least a short synthetic tail (e.g., last 10 points) so trend renders.
4. **Emit default empty objects/arrays explicitly** (`provider_breakdown`, `provider_reason_buckets`, `accounting_last_errors`, `internal_error_counts`, `integrity_last_samples`) to stabilize UI logic.
5. **Either add a logs panel to Jobs HTML or stop returning unused `logs`**; easiest operational fix is adding a small `<details>` log renderer bound to `logs`.

## Verification notes

Environment lacked Flask import dependencies, so endpoint execution was audited statically from source contracts instead of live HTTP calls.
