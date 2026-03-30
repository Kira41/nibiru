# Predicted Data Exchange & Module Links

This document outlines the predicted data relationships and workflow connections between the semi-independent modules inside the Nibiru project. Because the project is currently transitioning from a set of isolated scripts into a unified platform, these data links represent the **ideal target architecture** bridging the modules.

---

## 1. Spamhaus (Script 1) ⇔ Infrastructure (Script 3)

### The Context
Currently, an operator likely runs domains through Spamhaus (`script1`) and manually copies the "safe" domains into the Namecheap/PMTA Infrastructure tool (`script3`) for DNS setup.

### Deduced Data Link (How it should work)
The Infrastructure module should treat the Spamhaus cache (`spamhaus_cache.db`) as its upstream inventory source.
*   **Direction:** `Script 1` -> `Script 3` (Pull / Query)
*   **Data Exchanged:**
    *   `domain_name` (Target domain)
    *   `spamhaus_status` (Safe / Banned / Risky)
    *   `score` (Risk rating)
*   **The Workflow:** 
    When an operator opens the Infrastructure panel (`script3`) to configure a new server, the interface should provide a dropdown of **"Available Safe Domains"**. This dropdown queries the `script1` database directly. Once `script3` assigns the domain to a PMTA server and sets up DKIM/SPF, a callback updates the domain's status to "In Use" so `script1` knows it is deployed.

---

## 2. Spamhaus (Script 1) ⇔ Dashboard (Nibiru)

### The Context
The Nibiru dashboard serves as the central command center for the operator. It needs to know the health of the domain portfolio without the operator manually checking `script1`.

### Deduced Data Link (How it should work)
The dashboard requires an aggregated telemetry stream and a live-alerting link from the Spamhaus scanner. 
*   **Direction:** `Script 1` -> `Nibiru Dashboard` (Push / Polling)
*   **Data Exchanged:**
    *   `portfolio_health_metrics` (X Safe, Y At Risk, Z Banned)
    *   `live_blacklist_alerts` (Immediate Webhook/WebSocket notification)
*   **The Workflow:** 
    The Nibiru dashboard renders a "Domain Health" widget. It polls the `script1` backend API to display overall portfolio metrics. If a scheduled background task in `script1` detects that an actively sending domain has suddenly been blacklisted, it pushes an alert payload up to the Nibiru dashboard. The dashboard can then flash a red warning or even trigger an automatic pause on any active Send jobs relying on that domain.

---

## 3. Infrastructure / Send (Script 3) ⇔ Dashboard (Nibiru)

*(Note: While sending logic historically started in `script4`, it is now unified inside `nibiru.py`, while `script3` manages the physical PMTA/DNS infrastructure).*

### The Context
The operator uses the Nibiru dashboard to create and launch multi-server campaigns. However, Nibiru doesn't inherently know how to configure PMTA or which domains have active DNS records—that is the job of `script3`.

### Deduced Data Link (How it should work)
A highly synchronized, bidirectional relationship built on API endpoints and shared state (e.g., `script3.db`). The Dashboard orchestrates the campaign, but Infrastructure authorizes what can be used.
*   **Direction:** `Nibiru` ⇔ `Script 3` (Bidirectional)
*   **Data Exchanged:**
    *   **From Script 3 to Nibiru:** `authenticated_assets` (List of servers, IPs, and IPs tied to domains that have passed SPF/DKIM/DMARC checks).
    *   **From Nibiru to Script 3 / Send Engine:** `campaign_dispatch_orders` (SMTP targets, routing requests, payload chunks).
    *   **From Script 3 to Nibiru:** `pmta_live_status` (Is the server reachable via SSH? Is the queue backed up?).
*   **The Workflow:**
    1. **Pre-flight Check:** When launching a campaign from the Nibiru Send UI, Nibiru queries `script3` for all available infrastructure.
    2. **Verification:** `script3` responds with a list of servers where DKIM/SPF are confirmed as active and valid.
    3. **Execution:** Nibiru chunks the recipient lists and instructs the underlying execution engine to route emails through those specific `script3`-managed servers.
    4. **Live Monitoring:** The Nibiru dashboard continuously queries `script3`'s SSH connections to display live PMTA queue statuses (messages sent, deferred, etc.) directly on the dashboard.

---

## 4. Tracker (Script 5) ⇔ Send / Recipient Prep (Script 2)

### The Context
`script2` acts as the recipient list preparer and extractor, grouping and cleaning raw emails. For tracking to work, unique image pixel IDs and URLs must be generated for each verified recipient *before* the campaign is sent out.

### Deduced Data Link (How it should work)
The Tracker engine must intercept or accept payload lists from `script2` to append unique identifiers to them before they are ingested by the mailing module.
*   **Direction:** `Script 2` -> `Tracker (Script 5)` -> `Send Workflow` (Sequential Pipeline)
*   **Data Exchanged:**
    *   **From Script 2:** Cleaned `recipient_email_list` and `grouping_tags`.
    *   **From Tracker:** `tracked_recipient_list` (a joined dataset matching `email` -> `unique_hash_id` -> `image_pixel_url`).
*   **The Workflow:**
    When the operator finalizes a recipient list in `script2`, they press a "Generate Tracking Payload" action. This pipes the raw emails into `script5` / `tracker.db`. The Tracker generates a specific, persistent ID for each email and outputs the appended dataset to be used in the actual email HTML body during dispatch.

---

## 5. Tracker (Script 5) ⇔ Accounting (Script 6)

### The Context
The Tracker knows how many users opened the email. The Accounting tool (`script6`) knows how many emails bounced or successfully reached the recipient's inbox via PowerMTA logs. True open-rates require correlations between both numbers.

### Deduced Data Link (How it should work)
A synchronized analytics merge. To measure a genuine Open Rate (Opens vs. True Deliveries instead of Opens vs. Sent), `script5` and `script6` must merge their metrics around a common `campaign_id`.
*   **Direction:** `Accounting (Script 6)` ⇔ `Tracker (Script 5)` (Shared Analytics View)
*   **Data Exchanged:**
    *   **From Accounting (Script 6):** `total_delivered` (excluding bounces/deferrals) per Domain/Campaign.
    *   **From Tracker (Script 5):** `total_opens_captured` per Domain/Campaign.
*   **The Workflow:**
    At the conclusion of a send job, the unified backend imports PMTA logs into `script6` (Accounting). It then polls `tracker.db` to combine the data: Open Rate = `Tracker Opens` / `Accounting Delivered`. This provides the operator with an ultra-accurate domain health and campaign success report.

---

## 6. Tracker (Script 5) ⇔ Infrastructure (Script 3)

### The Context
To track opens, tracking pixel URLs must be hosted on specific domains. These domains need active DNS configurations (A-records/CNAMEs) pointing to the tracking server, which is the exact responsibility of `script3`.

### Deduced Data Link (How it should work)
The Tracker requires the Infrastructure manager to provision and verify tracking domains before it generates pixel URLs.
*   **Direction:** `Script 3` (Infra) -> `Tracker (Script 5)` (Provisioning)
*   **Data Exchanged:**
    *   **From Infra to Tracker:** `verified_tracking_domains` (List of domains mapped to the Tracker's IP block).
*   **The Workflow:**
    Before `script5` can generate the zipped package of tracking pixels, it queries `script3` to ask: "Which domains are actively pointing to our tracking server?" `script3` responds with a list of verified tracking domains. `script5` then safely embeds these authenticated target URLs into the outgoing recipient pixel IDs.

---

## 7. Tracker (Script 5) ⇔ Dashboard (Nibiru Dashboard)

### The Context
The operator using the main Nibiru Dashboard needs to visualize live engagement (who is opening emails, click timelines, etc.) in real-time, rather than manually parsing `image_log.jsonl` externally.

### Deduced Data Link (How it should work)
The Nibiru Dashboard needs a persistent API bridge into `tracker.db` to render real-time UI charts.
*   **Direction:** `Tracker (Script 5)` -> `Nibiru Dashboard` (Push / Polling API)
*   **Data Exchanged:**
    *   `live_open_events` (Timestamp, User-Agent, Matched Identifier).
    *   `aggregated_campaign_metrics` (X Opens in last hour).
*   **The Workflow:**
    A background service within the Tracker continuously monitors the `image_log.jsonl` file. When an open is recorded and matched against an identifier in `tracker.db`, it fires a WebSocket event to the Nibiru Dashboard. The Operator, sitting on the "Live Monitor" tab, sees the open statistics instantly graph upwards, giving immediate feedback on campaign performance.

---

## 8. Extractor (Script 2) ⇔ Dashboard (Nibiru Dashboard)

### The Context
`script2` extracts, processes, and prepares lists of email recipients. However, campaigns are actually crafted and launched from the Nibiru Dashboard. Currently, an operator likely has to manually copy/paste processed lists from `script2` into the mailer inputs on the Dashboard.

### Deduced Data Link (How it should work)
The Nibiru Dashboard should treat `script2` (Extractor) as its upstream provider for Campaign Recipient Groups.
*   **Direction:** `Script 2` -> `Nibiru Dashboard` (Pull / Payload Database)
*   **Data Exchanged:**
    *   `saved_audiences_list` (List of processed and categorized recipient groups).
    *   `audience_metadata` (e.g., total count, list breakdown by domain).
    *   `recipient_payload` (The actual formatted email array).
*   **The Workflow:**
    The Extractor saves processed and cleaned email cohorts into its database (`script2.db`) under named groups (e.g., "Active Users - Jan 2026"). When the operator goes to the Nibiru Dashboard to create a new Send Job, the interface features a dynamic "Select Audience" dropdown menu. The Dashboard API queries the Extractor to pull available audiences. Once selected, the Nibiru module securely references that processed payload directly during the send execution without any manual copying required.

---

## 9. Accounting (Script 6) ⇔ Dashboard (Nibiru)

### The Context
The Nibiru Dashboard needs to display live accounting and PMTA queue data, but it currently relies on hardcoded demo data or manual pulls. Script 6 is responsible for SSH connection to PMTA and processing CSV accounting logs.

### Deduced Data Link (How it should work)
The Dashboard should use Script 6 as its core engine for feeding real-time KPIs and live-monitoring alerts.
*   **Direction:** `Script 6` -> `Nibiru Dashboard` (Push / Polling)
*   **Data Exchanged:**
    *   `accounting.totals.bounced / delivered` (Real delivery metrics)
    *   `accounting.queue_snapshot.live_queue` (Queue depth)
    *   `job.pmta_outcomes` (Per-job delivery trends)
*   **The Workflow:**
    Instead of rendering static placeholders, the Dashboard periodically polls `script6` for a live `accounting_summary`. If the `bounce_rate` exceeds a certain threshold or the PMTA queue spikes unexpectedly, `script6` generates an alert payload that flashes on the Nibiru Dashboard, warning the operator. Progress bars for active Send Jobs consume real `delivered` counts from `script6` to update their completion percentage accurately.

---

## 10. Campaigns (Nibiru) ⇔ Dashboard (Nibiru)

### The Context
The `/campaigns` page holds the active list of sending jobs, while the main `/` Dashboard is supposed to be a live summary. Currently, the dashboard might show static demo campaigns.

### Deduced Data Link (How it should work)
A direct, in-memory state synchronization where the Dashboard acts simply as a visual projection of the `CAMPAIGNS_STATE`.
*   **Direction:** `Nibiru Campaigns` ⇔ `Nibiru Dashboard` (Shared State)
*   **Data Exchanged:**
    *   `CAMPAIGNS_STATE[0]` (The latest active campaign)
    *   `monitoring.sent / delivered / failed` (Real aggregated job metrics)
*   **The Workflow:**
    When an operator creates or starts a campaign in `/campaigns`, the `CAMPAIGNS_STATE` is updated. The Dashboard dynamically reads the most recently active campaign from this state, rendering its name, sender email, recipient counts, and a live progress bar dictated by the child jobs underneath it. If all jobs in a campaign finish, the Dashboard auto-transitions the campaign's status to "done".

---

## 11. Extractor (Script 2) ⇔ Accounting (Script 6)

### The Context
`script2` prepares the target recipient domains (where emails *will* go), while `script6` analyzes bounces and delivery rates for those recipient domains (where emails *actually went*).

### Deduced Data Link (How it should work)
A predictive and retroactive feedback loop. Accounting data should inform pre-send extraction quality, and Extractor volumes should inform Post-send accounting thresholds.
*   **Direction:** `Accounting (Script 6)` ⇔ `Extractor (Script 2)` (Bidirectional)
*   **Data Exchanged:**
    *   **From Accounting to Extractor:** `accounting_suppression_list` (Historical hard-bounces to scrub).
    *   **From Extractor to Accounting:** `planned_volume_per_domain` (How many emails are geared up for specific target domains).
*   **The Workflow:**
    Before a send, the operator loads an extracted list. The Extractor automatically queries `script6` for the global suppression list to pre-filter known bounced addresses. It also queries historical bounce rates per domain to show a "Health/Deliverability" badge next to each extracted group. In return, the Extractor tells Accounting "We are about to send 50,000 emails to Gmail," allowing Accounting to set dynamic volume-aware bounce-rate alert thresholds for that specific campaign.

---

## 12. Extractor (Script 2) ⇔ Infrastructure (Script 3)

### The Context
The Extractor organizes destination/recipient domains, while Infrastructure manages the origin/sender domains and IPs. They intersect at the level of capacity planning and IP warming.

### Deduced Data Link (How it should work)
Infrastructure needs the Extractor's volume breakdowns to plan server load, assign IPs intelligently, and execute domain warming schedules.
*   **Direction:** `Extractor (Script 2)` -> `Infrastructure (Script 3)` (Feed)
*   **Data Exchanged:**
    *   `extraction.grouped_domain_distribution` (Recipient volume breakdown).
    *   `spamhaus_listing_alerts` (From infra to extractor, signaling sender IP risks).
*   **The Workflow:**
    Once an extraction run is finished, the payload's domain distribution (e.g., 60% Google, 40% Yahoo) is passed to `script3`. Infrastructure uses this ratio to allocate sending IPs or generate a safe IP warming schedule. Conversely, if `script3` detects that the assigned sender IPs are currently flagged on Spamhaus for Yahoo, it warns the operator in the Extractor interface *before* they even attach that recipient list to a campaign.
