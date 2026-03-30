# Data Links Between Modules

This document maps every existing data exchange between the three module pairs and predicts the links that should exist once the project reaches full integration.

Legend:
- **[LIVE]** - Link exists and is functional in current code
- **[PARTIAL]** - Link exists but is incomplete, uses fallback, or is disconnected
- **[MISSING]** - Link should exist but does not; predicted based on architecture intent

---

## 1. Accounting (script6) <=> Dashboard (nibiru `/`)

### Current Data Flow

```
                     script6                                    nibiru dashboard
              ┌──────────────────┐                        ┌──────────────────────┐
              │ build_runtime    │──── ssh config ────────>│ DASHBOARD_DATA       │
              │   _config()      │<─── message_form ──────│   ["message_form"]   │
              │                  │                        │                      │
              │ render_dashboard │<─── namespace ─────────│ accounting_page()    │
              │   _page()        │<─── route_urls ────────│ /accounting routes   │
              │                  │<─── external_config ───│ DASHBOARD_DATA.      │
              │                  │                        │   message_form       │
              │ run_ssh_command()│<──── called by ────────│ load_pmta_monitor    │
              │                  │                        │   _snapshot()        │
              │ select_folder    │<──── called by ────────│ /accounting/select   │
              │   _action()      │                        │                      │
              │ refresh_action() │<──── called by ────────│ /accounting/refresh  │
              │ set_source_mode()│<──── called by ────────│ /accounting/use-ssh  │
              │                  │                        │ /accounting/use-local│
              │ download_action()│<──── called by ────────│ /accounting/download │
              └──────────────────┘                        └──────────────────────┘
```

### Existing Links

#### [LIVE] Accounting page rendered via script6 inside nibiru shell

`nibiru.py:6226-6240` — The `/accounting` route delegates rendering to `script6.render_dashboard_page()` with namespace `"nibiru_accounting"` and passes `DASHBOARD_DATA["message_form"]` as `external_config`. This is how accounting gets SSH settings from the dashboard.

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `DASHBOARD_DATA["message_form"]` | -> | `script6.build_runtime_config()` | `ssh_host`, `ssh_port`, `ssh_user`, `ssh_timeout` |
| `script6.render_dashboard_page()` | -> | `/accounting` response | Full analytics HTML |
| `/accounting/refresh` | -> | `script6.refresh_action()` | Triggers re-fetch from SSH or local |
| `/accounting/use-ssh` | -> | `script6.set_source_mode("ssh")` | Mode switch |
| `/accounting/use-local` | -> | `script6.set_source_mode("local")` | Mode switch |
| `/accounting/download/<kind>` | -> | `script6.download_action(kind)` | CSV/TXT report generation |

#### [LIVE] Accounting summary feeds dashboard KPIs

`nibiru.py:4841-4858` — `build_live_snapshot()` calls `build_accounting_summary()` and injects its output into the dashboard snapshot:

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `build_accounting_summary().totals.bounced` | -> | `snapshot["kpis"][3]` (Bounced) | Bounced count |
| `build_accounting_summary().queue_snapshot.live_queue` | -> | `snapshot["kpis"][7]` (Live Queue) | Queue depth |
| `build_accounting_summary()` (full) | -> | `snapshot["accounting"]` | Full accounting summary |

#### [LIVE] Dashboard page renders accounting card

`nibiru.py:5324-5349` — The dashboard template renders an "Accounting & PMTA" card showing:
- Delivered count and delivery rate from `accounting.totals`
- Bounced/deferred counts from `accounting.totals`
- Live queue and active jobs from `accounting.queue_snapshot`
- Top 4 recipient domains from `accounting.top_domains`
- Link to "Open Accounting Summary" (`/accounting`)

#### [LIVE] PMTA live monitoring uses script6 SSH helpers

`nibiru.py:3447,3566` — `load_pmta_monitor_snapshot()` calls `script6.build_runtime_config()` and `script6.run_ssh_command()` to fetch PMTA status/topqueues/backoff data over SSH.

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `script6.build_runtime_config()` | -> | `load_pmta_monitor_snapshot()` | SSH connection config |
| `script6.run_ssh_command()` | -> | `load_pmta_monitor_snapshot()` | Raw PMTA CLI output |

#### [PARTIAL] SSH config source disconnect

`nibiru.py` PMTA_LIVE_AUDIT.md documents this: Jobs PMTA monitor builds SSH config from static `DASHBOARD_DATA["message_form"]` instead of per-campaign form state. SSH settings entered on the Send page do not reach the Jobs PMTA monitor.

| Source | Direction | Target | Issue |
|--------|-----------|--------|-------|
| Send page SSH fields | ✘ | `load_pmta_monitor_snapshot()` | Config disconnect — should use `send_snapshot` or `CAMPAIGN_FORMS_STATE` |

#### [LIVE] `/api/accounting/ssh/status` endpoint

`nibiru.py:3012` (JS) — Jobs page polls `/api/accounting/ssh/status` for bridge connection badge and receiver diagnostic text.

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `load_pmta_monitor_snapshot()` | -> | `/api/accounting/ssh/status` response | `pmta_live`, `bridge_state`, `pmta_diag` |
| JS `bridgeDebugTick()` | <- | `/api/accounting/ssh/status` | Bridge connected/disconnected badge |

### Predicted Missing Links

#### [MISSING] Per-job accounting counters

Currently accounting is global (all PMTA traffic). It should be filtered by job identity (sender domain, campaign tag, `job_id` header, or accounting `category_path`).

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `script6.parse_csv_text()` filtered by job markers | -> | `build_job_detail().pmta_outcomes` | Per-job delivered/bounced/deferred |
| `job.send_snapshot.from_email` domain | -> | accounting row filter key | Filter accounting rows by sender domain |
| `job.id` or campaign tag | -> | accounting `category_path` match | Link PMTA rows to specific jobs |

#### [MISSING] Accounting-driven dashboard alerts

Dashboard alerts are currently hardcoded. They should be generated from live accounting analysis.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `accounting.totals.bounce_rate` | -> | `DASHBOARD_DATA["alerts"]` | Alert if bounce rate exceeds threshold |
| `accounting.queue_snapshot.live_queue` | -> | `DASHBOARD_DATA["alerts"]` | Alert if queue grows unexpectedly |
| `accounting.top_domains[].bounce_rate` | -> | `DASHBOARD_DATA["alerts"]` | Alert per-domain bounce spikes |

#### [MISSING] Accounting outcome_series for job trend charts

Jobs page expects `outcome_series` for sparkline trends but it is never populated.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Accounting time-bucketed rows | -> | `build_job_detail().outcome_series` | `[{ts, delivered, bounced, deferred, complained}]` |
| `script6.build_analysis().timeline_chart` | -> | Dashboard trend widget | Hourly delivery/bounce timeline |

#### [MISSING] Accounting-driven campaign status updates

Campaign status should reflect accounting reality (e.g., mark "done" when queue drains to 0).

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `accounting.queue_snapshot.live_queue == 0` | -> | `campaign["status"]` | Auto-transition from "running" to "done" |
| `accounting.totals.delivery_rate` | -> | `campaign_monitoring_snapshot()` | Real delivery rate in campaign card |

#### [MISSING] Dashboard progress bars from accounting

Dashboard progress (overall, domain, chunks, warmup) is currently hardcoded with jitter. Should be computed from accounting.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `accounting.totals.delivered / total_recipients` | -> | `snapshot["progress"]["overall"]` | Real overall progress percentage |
| Per-domain delivered / per-domain planned | -> | `snapshot["progress"]["domain"]` | Real domain completion progress |

#### [MISSING] SSH config from campaign form state

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `CAMPAIGN_FORMS_STATE[campaign_id].ssh_*` | -> | `load_pmta_monitor_snapshot()` | Campaign-aware SSH config |
| `job.send_snapshot.ssh_*` | -> | `load_pmta_monitor_snapshot()` | Job-stored SSH config |

---

## 2. Infra (script3) <=> Send (script4 / nibiru `/send`)

### Current Data Flow

```
              script3 (Infra)                              script4 / nibiru (Send)
          ┌──────────────────────┐                      ┌─────────────────────────┐
          │ shivaBridge config   │                      │                         │
          │   activeServerIds    │                      │  loadInfrastructure     │
          │   byServerId:       │                      │    Payload()            │
          │     domainIds       │──── localStorage ────>│  reads shivaBridge     │
          │     smtpHost/Port   │   shivaBridgePayload  │    PayloadV1           │
          │     smtpSecurity    │         V1            │                         │
          │     smtpUser/Pass   │                      │  consumeBridgeLaunch   │
          │   emailUsernames    │──── localStorage ────>│    Marker()             │
          │   senderNames       │   shivaBridgeLaunchV1 │  reads launch marker   │
          │                     │                      │                         │
          │ "Send to Shiva" btn │──── redirect ────────>│  /send page loads      │
          │  saves + navigates  │   window.location     │  with bridge payload   │
          │                     │   .assign('/send')    │                         │
          │                     │                      │                         │
          │ domain.selector     │                      │  _extract_dkim         │
          │ domain.spf          │──── infra_payload ───>│    _selector()          │
          │ domain.dmarc        │   (hidden form field) │  _extract_domain_auth  │
          │ domain.publicKey    │                      │    _expectations()      │
          │ domain.dkimTxt      │                      │  _extract_domain_mail  │
          │                     │                      │    _ips_from_infra()    │
          │ server.sshHost      │                      │                         │
          │ server.sshPort      │──── infra_payload ───>│  preflight DNS/auth    │
          │ server.sshUser      │                      │    check per domain     │
          └──────────────────────┘                      └─────────────────────────┘
```

### Existing Links

#### [LIVE] Shiva Bridge payload via localStorage

`script3.py:6276-6289` — When the operator clicks "Send to Shiva" in the infrastructure dashboard:

1. `collectShivaBridgeFromWorkspace()` gathers selected servers, domains, SMTP, SSH settings
2. `buildShivaPayloadForSend()` builds a structured payload
3. Payload written to `localStorage["shivaBridgePayloadV1"]`
4. Launch marker written to `localStorage["shivaBridgeLaunchV1"]` with `{source: "script3-send-to-shiva", createdAtMs: Date.now()}`
5. Data saved to backend via `saveData()`
6. Browser redirects to `/send`

`script4.py:580-602` — Send page on load:
1. `consumeBridgeLaunchMarker()` reads and validates the launch marker (2-minute expiry)
2. If valid: `loadInfrastructurePayload()` reads `localStorage["shivaBridgePayloadV1"]`
3. `renderInfrastructureCard(payload)` populates SMTP/SSH fields from first server
4. Sets `manual_send_mode = "0"` (automated mode)

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `shivaBridge.activeServerIds` | -> | Send page infrastructure card | Selected server IDs |
| `shivaBridge.byServerId[].smtpHost` | -> | Send form `smtp_host` | SMTP host auto-fill |
| `shivaBridge.byServerId[].smtpPort` | -> | Send form `smtp_port` | SMTP port auto-fill |
| `shivaBridge.byServerId[].smtpSecurity` | -> | Send form `smtp_security` | Security mode |
| `shivaBridge.byServerId[].smtpUser` | -> | Send form `smtp_user` | SMTP username |
| `shivaBridge.byServerId[].smtpPass` | -> | Send form `smtp_pass` | SMTP password |
| `shivaBridge.emailUsernames` | -> | Send form `from_email` | Sender emails |
| `shivaBridge.senderNames` | -> | Send form `from_name` | Sender names |
| Server SSH settings | -> | Send form SSH fields | SSH host/port/user |
| Domain list per server | -> | Infrastructure card display | Domain badges |

#### [LIVE] Infra payload carries domain auth expectations to preflight

`nibiru.py:5579-5657` — When the send page runs preflight, it passes the `infra_payload` hidden field. Three functions extract infrastructure data:

| Function | Reads From `infra_payload` | Extracts |
|----------|---------------------------|----------|
| `_extract_dkim_selector()` | `servers[].domains[].selector` | DKIM selector per domain |
| `_extract_domain_auth_expectations()` | `servers[].domains[].{spf, dmarc, publicKey, dkimTxt}` | Expected SPF/DKIM/DMARC values |
| `_extract_domain_mail_ips_from_infra()` | `servers[].domains[]` matched to `servers[].ips[]` | Mail-sending IPs per domain |

These feed into `_build_domain_dns_row()` and `_check_domain_auth_records()` which perform live DNS lookups and compare against infrastructure expectations.

#### [LIVE] Send snapshot captures infra-derived fields at job start

`nibiru.py:6734-6770` — When `/start` fires, it captures a `send_snapshot` and `runtime_config` from the form (which was auto-filled from infra):

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| Form fields (infra-derived) | -> | `new_job["send_snapshot"]` | `from_email`, `smtp_host`, `smtp_port`, `smtp_security`, `chunk_size` |
| Form fields or `CAMPAIGN_FORMS_STATE` | -> | `new_job["runtime_config"]` | SSH settings snapshot |

#### [LIVE] shivaBridge stored in script3 database

`script3.py:6622,6687-6697` — The `shivaBridge` object is persisted in the `app_storage` table as part of the full infrastructure JSON payload, so bridge configuration survives browser refreshes.

#### [PARTIAL] Infra payload not stored in send_snapshot

The `infra_payload` JSON (full bridge payload) is not saved into `send_snapshot` at job start time. Only individual field values are captured.

| Source | Direction | Target | Issue |
|--------|-----------|--------|-------|
| `infra_payload` (full JSON) | ✘ | `job.send_snapshot` | Full infra context lost after send start |

### Predicted Missing Links

#### [MISSING] Direct API bridge (replacing localStorage)

The current localStorage-based transfer is fragile (browser-only, 2-minute expiry, single-tab). A proper API bridge should exist.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `POST /api/bridge/payload` from script3 | -> | Server-side bridge store | Full shivaBridge payload |
| `GET /api/bridge/payload` from script4 | <- | Server-side bridge store | Retrieve latest bridge payload |
| Campaign form state `infra_payload` field | -> | `CAMPAIGN_FORMS_STATE[id]` | Persistent infra link per campaign |

#### [MISSING] Infra readiness status in send preflight

Script3 computes domain readiness (SPF/DKIM/DMARC/PTR verification). This should feed into send preflight automatically.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `domain.verification.status` from script3 | -> | Send preflight "ready" badges | Per-domain readiness flag |
| `domain.manualReadyOverride` | -> | Send preflight override | Force-ready flag |
| Infra readiness score | -> | Send preflight pass/fail | Block send if infrastructure not ready |

#### [MISSING] PMTA config sync status in send page

The send page should know whether PMTA config on the target server is current.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `server.pmtaConfigFingerprint` | -> | Send page config status badge | Config freshness indicator |
| `server.pmtaConfigPolledAt` | -> | Send page last-sync timestamp | When config was last pushed |

#### [MISSING] Domain registry lookup from send

Send page shows "In Use Domains" table but doesn't pull registry data (registrar, expiry) from script3.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `domainRegistry[].expiryDate` | -> | Send domains table "Expires" column | Domain expiry warning |
| `domainRegistry[].provider` | -> | Send domains table "Registrar" column | Registrar info |
| `domainRegistry[].note` (Spamhaus data) | -> | Send domains table "Reputation" column | Spamhaus score/status |

#### [MISSING] Send outcome feedback to infra

After sending, infrastructure should learn which domains performed well or poorly.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Job accounting per sender domain | -> | `domain.lastSendStats` in script3 | Delivery rate, bounce rate per domain |
| Blacklist detection during send | -> | `domain.verification.listings` | Real-time listing alerts |

#### [MISSING] Full infra_payload persistence in job

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `infra_payload` JSON | -> | `job.send_snapshot.infra_payload` | Full server/domain/IP context for diagnostics |
| `infra_payload.servers[].sshHost` | -> | `job.runtime_config.ssh_host` | SSH config for PMTA monitoring |

---

## 3. Campaigns (nibiru `/campaigns`) <=> Dashboard (nibiru `/`)

### Current Data Flow

```
        Campaigns Page                                  Dashboard Page
    ┌─────────────────────┐                        ┌──────────────────────┐
    │ CAMPAIGNS_STATE     │                        │ DASHBOARD_DATA       │
    │   (in-memory list)  │                        │   ["campaign"]       │
    │                     │                        │   (static demo obj)  │
    │ campaign_monitoring │                        │                      │
    │   _snapshot()       │──── reads JOBS ───────>│ build_live_snapshot()│
    │                     │                        │   reads DASHBOARD    │
    │ campaigns.json      │                        │   _DATA["campaign"]  │
    │   (persisted)       │                        │                      │
    │                     │                        │ _build_jobs_send     │
    │ CAMPAIGN_FORMS_STATE│                        │   _preview()         │
    │   (per-campaign)    │──── reads forms ──────>│   reads CAMPAIGNS    │
    │                     │                        │   _STATE + forms     │
    └─────────────────────┘                        └──────────────────────┘
```

### Existing Links

#### [LIVE] Campaign monitoring snapshot aggregates job data

`nibiru.py:4058-4083` — `campaign_monitoring_snapshot()` iterates `JOBS`, filters by `campaign_id`, and aggregates:

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `JOBS` (filtered by `campaign_id`) | -> | `monitoring.sent` | Sum of `job.sent` |
| `JOBS` (filtered) | -> | `monitoring.delivered` | Sum of `job.delivered` |
| `JOBS` (filtered) | -> | `monitoring.failed` | Sum of `job.failed` |
| `JOBS` (filtered) | -> | `monitoring.deferred` | Sum of `job.deferred` |
| `JOBS` (filtered) | -> | `monitoring.queued` | Sum of `job.queued` |
| `JOBS` count | -> | `monitoring.jobs_count` | Number of jobs |
| `campaign.total_recipients` | -> | `monitoring.total_recipients` | Max of stored total and inferred |
| `campaign.start_clicks` | -> | `monitoring.start_clicks` | Send button clicks |

This snapshot is rendered on each campaign card in `/campaigns`.

#### [LIVE] Dashboard send preview reads campaigns and forms

`nibiru.py:4875-4920` — `_build_jobs_send_preview()` reads `CAMPAIGNS_STATE` (latest campaign), its `CAMPAIGN_FORMS_STATE`, and the latest job:

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| `CAMPAIGNS_STATE[0]` (latest) | -> | `send_preview.campaign_name` | Campaign name in dashboard |
| `CAMPAIGN_FORMS_STATE[id].from_email` | -> | `send_preview.from_email` | Sender email display |
| `CAMPAIGN_FORMS_STATE[id].smtp_host` | -> | `send_preview.smtp_host` | SMTP host display |
| `CAMPAIGN_FORMS_STATE[id].subject` | -> | `send_preview.subject` | Subject preview |
| `CAMPAIGN_FORMS_STATE[id].domain_plan` | -> | `send_preview.top_domains` | Domain list |
| `campaign.total_recipients` | -> | `send_preview.total_recipients` | Recipient count |
| Latest job status | -> | `send_preview.status` | Job status badge |

#### [PARTIAL] Dashboard campaign sidebar uses static demo data

`nibiru.py:5191` — The dashboard renders `sidebar_campaign=DASHBOARD_DATA["campaign"]` which is static demo data, NOT the real `CAMPAIGNS_STATE`.

| Source | Direction | Target | Issue |
|--------|-----------|--------|-------|
| `DASHBOARD_DATA["campaign"]` (static demo) | -> | Dashboard campaign summary card | Shows hardcoded "Ramadan Promo" instead of real campaign |
| `CAMPAIGNS_STATE` (real data) | ✘ | Dashboard campaign summary | Not wired |

#### [LIVE] Start send updates campaign state

`nibiru.py:6824-6827` — When `/start` fires:

| Source | Direction | Target | Data |
|--------|-----------|--------|------|
| Start action | -> | `campaign["start_clicks"] += 1` | Increment click count |
| Start action | -> | `campaign["status"] = "running"` | Status transition |
| Updated state | -> | `save_campaigns(CAMPAIGNS_STATE)` | Persist to campaigns.json |

#### [LIVE] Campaign delete cleans up forms

`nibiru.py:6117-6125` — Deleting a campaign also removes its form state from `CAMPAIGN_FORMS_STATE`.

#### [LIVE] `/api/dashboard` returns live snapshot

`nibiru.py:6603` — Returns `build_live_snapshot()` which includes accounting-derived KPIs with jitter.

### Predicted Missing Links

#### [MISSING] Dashboard campaign card from real CAMPAIGNS_STATE

The dashboard campaign summary card should display the active/latest real campaign instead of static demo.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `CAMPAIGNS_STATE[0]` (latest active) | -> | Dashboard "Campaign summary" card | Real name, owner, status, ID |
| `campaign_monitoring_snapshot(latest)` | -> | Dashboard sent/delivered/failed counters | Real aggregated job metrics |
| `CAMPAIGN_FORMS_STATE[latest.id]` | -> | Dashboard "Message preview" section | Subject, from_email, body preview |

#### [MISSING] Dashboard KPIs from real campaign totals

KPIs are currently hardcoded demo values. They should reflect real campaign totals.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `sum(campaign.total_recipients for active campaigns)` | -> | `kpis[0]` (Total Recipients) | Real total |
| `sum(monitoring.delivered for active campaigns)` | -> | `kpis[1]` (Delivered) | Real delivered |
| `sum(monitoring.deferred for active campaigns)` | -> | `kpis[2]` (Deferred) | Real deferred |
| `sum(monitoring.failed for active campaigns)` | -> | `kpis[3]` (Bounced) | Real bounced |
| Computed from accounting per active campaign | -> | `kpis[4]` (Complaints) | Real complaint count |

#### [MISSING] Dashboard progress bars from campaign jobs

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `monitoring.sent / monitoring.total_recipients` | -> | `progress.overall` | Real overall progress |
| Per-domain sent/planned from job `domain_state` | -> | `progress.domain` | Real domain progress |
| `job.chunks_done / job.chunks_total` | -> | `progress.chunks` | Real chunk progress |

#### [MISSING] Dashboard alerts from campaign events

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `job.diagnostics["pmta_live"]` | -> | Alert: "PMTA bridge disconnected" | Bridge health alert |
| `job.status == "error"` | -> | Alert: "Job failed" | Error alert |
| `campaign.status == "backoff"` | -> | Alert: "Adaptive throttle active" | Throttle alert |
| Domain bounce rate spikes | -> | Alert: "Domain X exceeding bounce threshold" | Per-domain alert |

#### [MISSING] Campaign list reflects accounting delivery stats

Currently campaigns page shows `monitoring.delivered` from in-memory job counters. Should also include accounting-verified numbers.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `accounting` filtered by campaign sender domains | -> | Campaign card "Delivery rate" | Accounting-verified delivery rate |
| `accounting.suppression_list` per campaign | -> | Campaign card "Suppressions" | Bounced recipients to suppress |

#### [MISSING] Dashboard ops_snapshot from real operations

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `len([j for j in JOBS if j["status"] == "running"])` | -> | `ops_snapshot` "Active jobs" | Real running job count |
| `accounting.queue_snapshot.live_queue` | -> | `ops_snapshot` "Live queue" | Real queue depth |
| Bridge poll interval from config | -> | `ops_snapshot` "Bridge poll" | Real polling interval |

#### [MISSING] Campaign status auto-transitions from job lifecycle

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| All jobs for campaign are "done" | -> | `campaign["status"] = "done"` | Auto-complete campaign |
| Any job enters "error" | -> | `campaign["status"] = "error"` | Propagate error state |
| Any job enters "paused" | -> | `campaign["status"] = "paused"` | Reflect pause |
| New job created for campaign | -> | `campaign["status"] = "running"` | Already implemented |

#### [MISSING] Dashboard campaign list summary

Dashboard should show a compact campaign list with status indicators.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `CAMPAIGNS_STATE` with monitoring | -> | Dashboard sidebar "Campaigns" | Status badges, last activity, recipient counts |
| Click on campaign row | -> | Navigate to `/campaigns` or `/send?campaign=X` | Quick access |

---

## 4. Campaigns (nibiru `/campaigns`) <=> Extractor (script2 `/extractor`)

> **Note:** Script2 is the **Email Domain Extractor** tool. It groups email lists by recipient domain, not the SMTP send module (which is script4). The link between campaigns and the extractor is about **recipient list preparation**.

### Current Data Flow

```
        Campaigns Page                                  Extractor (script2)
    +---------------------+                        +------------------------+
    | CAMPAIGNS_STATE     |                        | extraction_runs table  |
    |   (in-memory list)  |                        |   (script2.db)         |
    |                     |                        |                        |
    | CAMPAIGN_FORMS_STATE|                        | grouped email output   |
    |   recipients field  |     (NO LINK TODAY)    |   by domain            |
    |   domain_plan       |   ......................|   duplicates report    |
    |                     |                        |   invalid report       |
    |                     |                        |                        |
    | /send page          |                        | Selected Groups        |
    |   recipients        |     (manual copy/paste)|   Preview textarea     |
    |   textarea          |<- - - - - - - - - - - -|   (user copies text)   |
    +---------------------+                        +------------------------+
```

### Existing Links

**No direct code links exist.** Script2 is not imported by the campaigns system, and campaigns state is not read by script2. The only connection today is the **human operator** who uses the extractor to prepare email lists and then manually pastes them into the send page recipients textarea.

Both modules appear in the nibiru navigation bar (`nibiru.py:142` registers `"extractor"` nav item), but no data flows between them programmatically.

### Predicted Missing Links

#### [MISSING] Import extraction run into campaign recipients

The extractor saves complete extraction runs to `script2.db` (`extraction_runs` table) with grouped emails, domains, and settings. The send form (`script4.py:406`) has a `recipients` textarea. A direct import path should exist.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction_runs.payload.extraction.uniqueEmails` | -> | Send form `recipients` textarea | Full deduplicated email list |
| `extraction_runs.payload.extraction.grouped` | -> | Send form `recipients` (filtered) | Emails from selected domain groups only |
| `extraction_runs.payload.extraction.selected` | -> | Import filter | Which domain groups the operator chose |

#### [MISSING] Extraction run ID linked to campaign form state

`CAMPAIGN_FORMS_STATE[campaign_id]` (`nibiru.py:4020`) stores per-campaign form data. It should record which extraction run sourced the recipient list.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction_runs.id` | -> | `CAMPAIGN_FORMS_STATE[id].extraction_run_id` | Link to source extraction run |
| `extraction_runs.payload.summary` | -> | `CAMPAIGN_FORMS_STATE[id].extraction_summary` | Total emails, unique, duplicates removed |
| Campaign delete | -> | Extraction run reference cleanup | Unlink (not delete) extraction run |

#### [MISSING] Extractor domain grouping feeds campaign domain_plan

The extractor groups emails by domain (e.g., gmail: 500, yahoo: 300, outlook: 200). The jobs system uses `domain_plan` (`nibiru.py:4247`) to distribute sending across domains. These should be connected.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction.grouped[domain].emails.length` | -> | `job.domain_plan[domain]` as `planned` | Per-domain planned recipient count |
| `extraction.grouped` keys | -> | `job.top_domains` | Recipient domain priority list |
| Provider grouping (gmail/yahoo/etc) | -> | Campaign send preview `top_domains` | Provider distribution for preview card |

#### [MISSING] Recipient quality report from extractor in campaign card

The extractor computes quality metrics (duplicates removed, invalid entries, unique count). These should appear in the campaign card before send.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction.summary.duplicatesRemoved` | -> | Campaign card "Quality" section | Duplicates cleaned count |
| `extraction.summary.invalidEntries` | -> | Campaign card "Quality" section | Invalid emails removed count |
| `extraction.summary.uniqueEmails` | -> | `campaign.total_recipients` | Verified unique recipient count |

#### [MISSING] Bidirectional navigation with context

The campaigns page should link to the extractor with context (e.g., "Prepare recipients for this campaign"), and the extractor should offer a "Send to Campaign" button after extraction.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Campaign card "Prepare recipients" link | -> | `/extractor?campaign_id=X` | Open extractor in campaign context |
| Extractor "Send to Campaign" button | -> | `/send?campaign_id=X&extraction_run=Y` | Push extraction into campaign |
| Extractor nav breadcrumb | <- | Campaign context | Show which campaign is being prepared |

#### [MISSING] Extract-and-send pipeline (one-click flow)

Similar to the Shiva Bridge between script3 and script4, an **Extractor Bridge** should allow one-click flow from extraction results to the send form.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `localStorage["extractorBridgePayloadV1"]` | -> | Send page `recipients` | Selected/all extracted emails |
| `localStorage["extractorBridgeLaunchV1"]` | -> | Send page auto-fill trigger | Launch marker (like shivaBridge) |
| Extractor "Send Selected" button | -> | `/send?campaign_id=X` redirect | Redirects with bridge payload set |

---

## 5. Extractor (script2) <=> Accounting (script6)

> The extractor groups **inbound** email lists by **recipient domain** (where emails will be delivered). Accounting analyzes **outbound** delivery results by **recipient domain** (where emails were actually delivered/bounced). These two modules operate on the same domain axis but at different pipeline stages: **before send** vs **after send**.

### Current Data Flow

```
     Extractor (script2)                              Accounting (script6)
  +------------------------+                      +---------------------------+
  | extraction_runs table  |                      | PMTA accounting CSV data  |
  |   grouped by           |                      |   parsed by               |
  |   recipient domain     |   (NO LINK TODAY)    |   build_analysis()        |
  |                        |  .....................|                           |
  | gmail: 500 emails      |                      | gmail.com: 480 delivered  |
  | yahoo: 300 emails      |                      | yahoo.com: 250 delivered  |
  | outlook: 200 emails    |                      | outlook.com: 190 delivered|
  |                        |                      |                           |
  | duplicates report      |                      | bounce categories         |
  | invalid entries        |                      | suppression candidates    |
  | quality metrics        |                      | delivery rates per domain |
  +------------------------+                      +---------------------------+
```

### Existing Links

**No direct code links exist.** Script6 does not import or reference script2. Script2 does not reference script6. They share the concept of "recipient domain" as a grouping key but operate independently.

Accounting's `recipient_domain_rows` (`script6.py:1548-1575`) track per-domain delivery stats. The extractor's `grouped` output (`script2.py:913` JS `state.grouped`) groups input emails by domain. These are the same domains viewed from opposite ends of the pipeline.

### Predicted Missing Links

#### [MISSING] Accounting bounce data validates extractor domain quality

Before sending, the operator prepares a recipient list in the extractor. Accounting has historical delivery stats per recipient domain. These stats should flag problematic domains.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `accounting.recipient_domain_rows[].bounce_rate` | -> | Extractor domain card "Health" badge | Historical bounce rate per domain |
| `accounting.recipient_domain_rows[].worst_category` | -> | Extractor domain card tooltip | Most common bounce reason |
| `accounting.recipient_domain_rows[].delivered` | -> | Extractor domain card "Past delivery" metric | Historical deliverability |

#### [MISSING] Accounting suppression list filters extractor output

Accounting identifies bounced recipients (`script6.py:1351` — records with `result=bounced`). These should be available as a suppression list to pre-filter extraction results.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Accounting bounced recipients | -> | Extractor "Suppress" filter | Remove known-bad addresses before send |
| Accounting hard-bounce list | -> | Extractor card warning badge | Flag domains with high hard-bounce history |
| `nibiru.build_accounting_summary().totals.bounced` | -> | Extractor quality sidebar metric | "Previously bounced" count overlay |

#### [MISSING] Extractor domain volume forecasts accounting alert thresholds

The extractor knows how many emails will go to each domain. Accounting should use this to predict queue pressure and set alert thresholds.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction.grouped[domain].emails.length` | -> | Accounting predicted volume per domain | Expected traffic volume |
| Extraction total unique count | -> | Accounting expected total | Baseline for delivery rate calculation |
| Domain group distribution | -> | Accounting alert thresholds | Per-domain volume-aware bounce thresholds |

#### [MISSING] Post-send reconciliation (extractor input vs accounting outcomes)

After a campaign completes, a reconciliation view should compare extractor input (planned) vs accounting output (actual).

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction.grouped[domain].emails.length` as `planned` | <-> | `accounting.recipient_domain_rows[domain].total` as `actual` | Planned vs actual per domain |
| `extraction.summary.uniqueEmails` as total planned | <-> | `accounting.summary.total_rows` as total processed | Overall planned vs processed |
| Reconciliation delta | -> | Campaign monitoring "Reconciliation" tab | Domain-by-domain delivery report |

#### [MISSING] Accounting recipient domain stats enrich extractor domain cards

The extractor currently labels domain cards with provider aliases (Google, Microsoft, Yahoo). Accounting can add delivery reputation data.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `accounting.recipient_domain_rows[].delivery_rate` | -> | Extractor domain card "Deliverability" score | Historical delivery rate |
| `accounting.recipient_domain_rows[].top_mx` | -> | Extractor domain card MX info | Destination mail servers |
| `accounting.recipient_domain_rows[].top_bounce_reason` | -> | Extractor domain card risk indicator | Common rejection reason |

---

## 6. Extractor (script2) <=> Infra (script3)

> The extractor groups emails by **recipient domain** (destination). Infra manages **sender domains** (origin — SPF, DKIM, DMARC, DNS, IPs). These are conceptually different domain types, but they intersect at **sender-recipient alignment** (e.g., which sender domains/IPs will deliver to which recipient domains).

### Current Data Flow

```
     Extractor (script2)                                Infra (script3)
  +------------------------+                      +---------------------------+
  | recipient domains      |                      | sender domains            |
  |   gmail.com            |   (NO LINK TODAY)    |   mydomain.com            |
  |   yahoo.com            |  .....................|   mydomain2.com           |
  |   outlook.com          |                      |                           |
  |                        |                      | servers[]                 |
  | email volume per       |                      |   IPs, SSH, SMTP          |
  |   recipient domain     |                      |   domain verification     |
  |                        |                      |   SPF/DKIM/DMARC/PTR     |
  |                        |                      |                           |
  | quality metrics        |                      | shivaBridge payload       |
  |   duplicates/invalid   |                      |   (to send page)          |
  +------------------------+                      +---------------------------+
```

### Existing Links

**No direct code links exist.** Script3 does not import or reference script2. Script2 does not reference script3. They manage different domain namespaces (recipient vs sender) and have no shared data stores.

The only indirect overlap is that both feed the send page: script3 provides sender infrastructure (via Shiva Bridge / `localStorage`), and script2 produces recipient lists (currently via manual copy/paste).

### Predicted Missing Links

#### [MISSING] Recipient volume from extractor informs infra capacity planning

Infra manages server/IP/domain infrastructure. Knowing the recipient volume distribution helps plan IP allocation and domain rotation.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction.grouped[domain].emails.length` | -> | Infra capacity planner | Expected recipients per destination domain |
| Extraction total unique count | -> | Infra server load estimator | Total send volume for infrastructure sizing |
| Top recipient domains (gmail/yahoo/etc) | -> | Infra domain priority | Which destination domains need most capacity |

#### [MISSING] Extractor domain distribution informs IP warming strategy

IP warming requires gradually increasing volume per destination domain. The extractor's domain breakdown is the input for warming schedules.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| `extraction.grouped` distribution | -> | Infra warming schedule generator | Volume ramp per destination domain |
| Provider proportions (Google 50%, Yahoo 30%) | -> | Infra IP rotation config | IP allocation proportional to recipient mix |
| Extraction date/time | -> | Warming timeline start | When warming should begin |

#### [MISSING] Infra DNS/auth data enriches extractor domain cards

Infra verifies sender domain DNS (SPF, DKIM, DMARC). While these are sender records, alignment checks require knowing the recipient domain's acceptance policies. Infra could enrich the extractor view.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Infra sender domain `verified` status | -> | Extractor "Sender readiness" indicator | Whether sender domains are auth-ready |
| Infra `server[].domains[].selector` (DKIM) | -> | Extractor enrichment sidebar | DKIM signing status per sender domain |
| Infra server count / IP count | -> | Extractor capacity badge | Available infrastructure summary |

#### [MISSING] Bidirectional domain health dashboard

A unified domain health view should combine sender domain status (infra) with recipient domain reputation (extractor + accounting).

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Infra sender domains + verification status | -> | Unified domain dashboard "Sender" column | SPF/DKIM/DMARC pass/fail |
| Extractor recipient domains + volume | -> | Unified domain dashboard "Recipient" column | Target domains + email count |
| Accounting delivery stats per domain | -> | Unified domain dashboard "Performance" column | Delivery/bounce rates |

#### [MISSING] Infra Spamhaus results feed extractor domain risk

Script1 (Spamhaus checker) is connected to script3 via `api_poll_infra()` (`nibiru.py:6314-6316`). Spamhaus listings of sender IPs affect deliverability to specific recipient domains. This should surface in the extractor.

| Source | Direction | Target | Predicted Data |
|--------|-----------|--------|----------------|
| Spamhaus listing for sender IP | -> | Extractor domain card "Risk" indicator | Sender IP blacklisted — delivery to this domain at risk |
| Infra `server[].ips[].listings` | -> | Extractor sidebar risk summary | "X sender IPs are listed — Y recipient domains may be affected" |

---

## Summary: Integration Priority

### High Priority (required for operational use)

1. **Dashboard <- real CAMPAIGNS_STATE** — Replace static `DASHBOARD_DATA["campaign"]` with latest active campaign
2. **Dashboard KPIs <- campaign monitoring + accounting** — Replace hardcoded numbers with real aggregated data
3. **Job PMTA monitoring <- campaign SSH config** — Fix SSH config disconnect (use `send_snapshot` or `CAMPAIGN_FORMS_STATE`)
4. **Accounting -> per-job filtering** — Filter accounting rows by job identity markers
5. **Extractor -> Campaign recipients import** — Direct import path from extraction runs into campaign send form

### Medium Priority (improves reliability)

6. **Infra -> Send: API bridge** — Replace localStorage with server-side bridge endpoint
7. **Accounting -> Dashboard alerts** — Generate alerts from bounce rates, queue depth, domain health
8. **Job -> outcome_series** — Populate time-series from accounting for trend charts
9. **Campaign status auto-transitions** — Derive status from child job lifecycle
10. **Extractor -> domain_plan** — Feed extractor domain grouping into job domain distribution plan
11. **Accounting -> Extractor domain health** — Historical bounce data enriches extractor domain cards
12. **Extractor -> Accounting reconciliation** — Compare planned recipients vs actual delivery per domain

### Lower Priority (enrichment)

13. **Infra readiness -> Send preflight** — Block send if infrastructure not ready
14. **Send outcomes -> Infra feedback** — Feed delivery stats back to domain records
15. **Domain registry -> Send domains table** — Show registrar, expiry, Spamhaus data
16. **Dashboard ops_snapshot** — Populate from real job and accounting state
17. **Extractor Bridge** — localStorage bridge (like shivaBridge) from extractor to send page
18. **Extractor + Infra capacity** — Recipient volume distribution informs IP/domain capacity planning
19. **Accounting suppression -> Extractor** — Pre-filter extraction results with known-bounced addresses
20. **Unified domain health** — Combined sender (infra) + recipient (extractor) + performance (accounting) view
