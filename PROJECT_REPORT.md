# Nibiru Project Report

## Overview

This document summarizes the current state of the repository, the real functional purpose of each script, the relationships between the tools, the duplication that exists today, and the recommended roadmap for turning the current collection of local tools into a more coherent integrated system.

The project today is not a single unified application. It is a collection of local operational tools used across the lifecycle of email campaigns:

1. sender domain screening,
2. recipient list preparation,
3. infrastructure and DNS automation,
4. campaign sending orchestration,
5. email-open tracking,
6. accounting and delivery analytics.

The current system is heavily workflow-driven and mostly connected manually through copy/paste, local SQLite databases, and exported/generated artifacts.

---

## High-Level Goal of the Project

The overall goal is to build a unified local control system for email campaign operations that can help with:

- selecting safe and usable sender domains,
- preparing recipient lists,
- managing infrastructure (domains, servers, IPs, DNS, DKIM, PMTA configuration),
- orchestrating sending campaigns across multiple servers,
- tracking opens through generated image identifiers,
- analyzing post-send accounting data and delivery performance.

The long-term vision is not merely to keep independent scripts, but to progressively move toward a more unified operational platform while preserving the workflows that are already useful in production.

---

## Current Repository Structure

### `script1.py`
Sender-domain screening tool using Spamhaus.

### `script2.html`
Recipient list extractor/grouping tool.

### `script3.py`
Core infrastructure control and automation panel.

### `script4.html`
Mailer front-end design / sending control interface prototype.

### `script5.py`
Email-open tracking generator and stay/open monitoring tool.

### `script6.py`
PowerMTA accounting analytics dashboard.

### `nibiru.py`
Current aggregation attempt / shell frontend that already includes parts of the mailer UI and monitoring-oriented views.

---

## Detailed Functional Meaning of Each Script

## 1. `script1.py` — Sender Domain Screening

### Functional purpose
This tool is used to screen candidate sender domains through the Spamhaus API.

### Real workflow
- A list of domains is pasted manually into a text area.
- The operator clicks a scan/start action.
- The script checks those domains and returns results such as score, availability, and related domain reputation information.
- Results are stored in a local SQLite database.
- The operator later exports CSV manually and chooses which domains should be used later in the broader system.

### Why it exists
Its role is not to send campaigns and not to manage infrastructure directly. Its purpose is to **filter sender domains before they are adopted elsewhere**.

### Important notes
- It is local-use only.
- No login or multi-user behavior is required.
- Selection is still manual.
- The transition from this tool to the next stage is currently done through copy/paste or manual export/import.

### Current role in the ecosystem
**Sender-side qualification tool.**

---

## 2. `script2.html` — Recipient Email Extractor / Grouping Tool

### Functional purpose
This tool cleans recipient emails, groups them by domain and other configurable grouping rules, and prepares selected outputs for later use.

### Real workflow
- Raw recipient emails are pasted into a text area.
- The script extracts and groups emails.
- The user selects useful groups.
- The script prepares a copyable final list of recipient emails.
- That output is pasted manually into another tool later.

### Notes about storage
Today this script is still front-end only and uses browser local storage. There is no finalized database implementation for it yet.

### Planned future direction
A real database may be added later, either:
- as its own store,
- or as part of a bigger unified database after architecture decisions are finalized.

### Current role in the ecosystem
**Recipient-side list preparation tool.**

---

## 3. `script3.py` — Infrastructure Control Plane / Automation Hub

### Functional purpose
This is the heart of the project.

It manages:
- domains,
- servers,
- additional IPs,
- DNS records,
- Namecheap interactions,
- DKIM generation,
- PowerMTA configuration generation,
- readiness checks,
- infrastructure overview,
- DNS verification,
- automation around SPF / DKIM / DMARC.

### Real workflow
This tool acts as the main infrastructure dashboard where operational assets are created, edited, validated, and linked together.

It can:
- store infrastructure entities in a main SQLite database,
- connect to Namecheap,
- write and modify DNS records through the registrar API,
- connect to servers via SSH,
- generate and push operational artifacts,
- generate PMTA configuration output,
- keep infrastructure state inside its main DB.

### Domain Registry
The domain registry is not separate from the infrastructure tree conceptually; it is part of the same infrastructure system and is used later when domains are linked to servers and IPs.

### Automation behavior
When a domain and server are selected, the tool can automate or assist with:
- SPF,
- DKIM,
- DMARC,
- registrar updates,
- dashboard refresh/update,
- infrastructure synchronization.

### Current role in the ecosystem
**Core infrastructure backbone and automation engine.**

This is currently the strongest candidate for the long-term backend core of the whole system.

---

## 4. `script4.html` — Mailer / Sending Orchestrator UI

### Functional purpose
This is the mailer interface used to define and run sending campaigns.

### Important current status
This file is currently **front-end only**. The operational backend behind it is not yet properly completed inside this file.

### Real intended behavior
This tool is supposed to:
- receive recipient lists from the recipient-preparation workflow,
- receive domains and server-related data from the infrastructure workflow,
- define senders, servers, campaigns, SMTP data, message content, and delivery logic,
- manage jobs,
- monitor sending,
- handle pause/resume/stop/delete,
- use AI-assisted rewriting,
- perform preflight checks,
- evaluate blacklist/message/link conditions,
- distribute sending load across multiple servers,
- keep everything stored in its own database.

### PowerMTA relationship
This mailer is not meant to send through a single local process only.

The real model is:
- the control panel runs locally or on its own host,
- PowerMTA exists on one or more external sending servers,
- SMTP is used for sending,
- SSH is used for monitoring and operational retrieval.

### Live monitoring behavior
This panel is intended to use:
- live PowerMTA monitoring through SSH commands,
- accounting-based analysis,
- job telemetry,
- adaptive orchestration logic based on campaign state and responses.

### Relationship to `nibiru.py`
The send UI that appears inside `nibiru.py` is effectively the same mailer UI that was placed there as part of an early attempt to unify interfaces.

### Current role in the ecosystem
**Campaign sending orchestrator and execution control surface.**

---

## 5. `script5.py` — Email Open Tracking / Stay Monitoring

### Functional purpose
This tool tracks email opens through generated image assets.

### Real workflow
- A campaign recipient list is provided.
- Each email receives a unique persistent numeric identifier.
- A tracking image is generated per recipient.
- The images and supporting tracking files are packaged into a ZIP.
- The ZIP is uploaded manually to the customer's or campaign server.
- When the email is opened, the image is requested from that external server.
- The server records the image access in `image_log.jsonl`.
- The tool later reads those logs and matches the logged identifier back to the email using its own database.

### Important relationship with the mailer
This script and the mailer are not fully separate logically.
They share the same identifier-generation logic for tracking opens.

The mailer embeds URLs pointing to tracking images, while the tracker resolves those image-open events back to recipient identities.

### What it analyzes
The main outcomes that matter here are:
- opened emails,
- opened domains,
- per-domain activity,
- activity timeline,
- future retargeting and segmentation.

### Current role in the ecosystem
**Open-tracking resolution engine and engagement analytics input source.**

---

## 6. `script6.py` — PowerMTA Accounting Analytics Dashboard

### Functional purpose
This tool analyzes PowerMTA accounting CSV files collected from one or more sending servers.

### Real workflow
- Accounting CSV files are downloaded manually from multiple PowerMTA servers.
- Those files are placed together into one folder.
- The operator selects that folder from the dashboard.
- The tool parses all available accounting files and builds a local analytics view.

### Reported outputs
It provides:
- delivery/OK metrics,
- bounce counts,
- recipient-domain analysis,
- sender-domain performance,
- infrastructure diagnostics,
- bounce categories,
- timeline analysis,
- recent bounce events,
- downloadable summaries and CSV exports,
- suggestions and operational improvement hints.

### Current role in the ecosystem
**Post-send accounting analytics and diagnostics dashboard.**

---

## 7. `nibiru.py` — Current Aggregation Attempt / Unified Shell Prototype

### Functional purpose
`nibiru.py` is currently a shell-like Flask aggregation attempt that combines multiple frontend concepts into a single interface.

### What it currently represents
It includes frontend-oriented views such as:
- dashboard,
- send page,
- campaigns,
- jobs,
- job details,
- config,
- domains,
- fake/live-like monitoring surfaces.

### Important current limitation
At this stage it is largely a UI/prototype shell and not yet the true integrated backend of the project.

### Why it still matters
Even though much of it is currently placeholder/fake oriented, it already expresses the intended unified operator experience and can serve as the target shell for future integration.

### Current role in the ecosystem
**Early unified application shell / frontend consolidation prototype.**

---

## How the Scripts Relate to Each Other Today

Today the scripts are mostly connected manually.

### Current end-to-end mental flow
1. `script1.py` helps choose sender domains.
2. `script2.html` prepares recipient email lists.
3. `script3.py` stores and manages infrastructure assets and operational configuration.
4. `script4.html` / the send UI inside `nibiru.py` orchestrates campaigns and delivery.
5. `script5.py` tracks opens after sending.
6. `script6.py` analyzes post-send accounting and delivery performance.

### Important current reality
The workflow works, but it is **operator-mediated**.
The user performs multiple copy/paste and manual movement steps between tools.

---

## Present Architectural Reality

The project today is best described as:

### A local operational toolkit composed of multiple semi-independent systems
Characteristics:
- multiple standalone tools,
- multiple local databases,
- minimal automatic integration,
- local/manual workflows,
- duplicate checks in different places for safety and convenience,
- gradual attempts toward unification.

This is not accidental; it reflects how the tools evolved while remaining usable independently.

---

## What Is Missing Today

## 1. No unified architecture yet
There is no finalized shared application structure such as:
- services,
- blueprints/modules,
- common models,
- central configuration strategy,
- unified persistence contract.

## 2. No central dependency manifest in the repository root
There is no single visible root packaging/dependency file describing the whole project.

## 3. Multiple isolated SQLite databases
Each tool largely keeps its own data locally.
That is useful for independence, but it also creates duplication and integration friction.

## 4. Repeated logic across tools
Some business logic exists in more than one place today, for example:
- sender/domain checks,
- saved domains,
- tracking identifier logic,
- campaign-related persistence ideas,
- diagnostics and monitoring concepts.

## 5. Manual transitions between tools
The workflow depends heavily on manual transfer:
- copy/paste,
- CSV export/import,
- ZIP generation and manual upload,
- folder selection,
- manual accounting collection.

## 6. Some components are still UI-first prototypes
Most notably:
- `script4.html`,
- portions of `nibiru.py`.

## 7. Need for shared operational contracts
The future unified system will need common contracts for:
- domains,
- servers,
- IPs,
- campaigns,
- jobs,
- recipients,
- tracking IDs,
- event timelines,
- accounting outcomes.

---

## What the Future Unified Project Should Become

A good long-term target is:

## A local unified campaign operations platform
with modules such as:

### Core modules
- Domain Screening
- Recipient Preparation
- Infrastructure Management
- Sending Orchestration
- Tracking & Open Monitoring
- Accounting Analytics
- Unified Jobs / Monitoring / Logs
- Shared Config and Operational Rules

### Likely application shell
`nibiru.py` (or a refactored successor of it) is the most natural place to become the final operator shell because it already expresses the desired multi-surface workflow.

### Likely backend core
The backend logic most likely should be centered around the concepts already present in `script3.py`, because it is the strongest infrastructure control point today.

---

## Recommended Integration Strategy

## Recommendation: do NOT merge everything blindly at once
The best path is **not** to directly merge all scripts into one giant file or one immediate monolith.

Instead, the best path is:

## Stabilize → Modularize → Integrate

### Why this is the best option
Because direct merge now would preserve current duplication and produce a fragile system with:
- mixed responsibilities,
- route collisions,
- repeated persistence logic,
- unclear contracts,
- hard-to-maintain code.

---

## Proposed Future Steps

## Phase 1 — Documentation and Architecture Freeze
Before major refactoring:
- define the target product clearly,
- document module boundaries,
- define shared data concepts,
- define which script becomes which module.

### Deliverables
- architecture map,
- shared vocabulary,
- data model inventory,
- route/module map,
- integration priority list.

---

## Phase 2 — Choose System Roles
Recommended role assignment:

### `script1.py`
Becomes **Domain Screening module/service**.

### `script2.html`
Becomes **Recipient Preparation UI/module**.
Likely later backed by real database support.

### `script3.py`
Becomes **Infrastructure Core / Automation backend**.

### `script4.html`
Becomes **Mailer UI specification** and later part of the unified send module.

### `script5.py`
Becomes **Tracking service/module** with shared tracking-ID logic.

### `script6.py`
Becomes **Accounting Analytics module**.

### `nibiru.py`
Becomes **Unified shell / application entrypoint**.

---

## Phase 3 — Extract Shared Logic
Some logic should be centralized instead of duplicated.

Examples:
- sender domain status and checks,
- tracking-ID generation,
- campaign/job state model,
- domain/server/IP references,
- provider/accounting interpretation helpers.

This phase should create shared services/helpers rather than keeping the same logic in multiple tools.

---

## Phase 4 — Unify Persistence Strategy
A major architectural decision will be required:

### Option A — keep separate stores per module
Useful for independence, but increases integration work.

### Option B — create a shared central database
Useful for unification, workflow continuity, and historical linking.

### Likely recommendation
Adopt a **central operational database** for core entities, while still allowing some cache tables or module-local temporary storage where useful.

Central entities would likely include:
- campaigns,
- recipients,
- sender domains,
- infrastructure assets,
- jobs,
- tracking mappings,
- accounting imports,
- analytics snapshots.

---

## Phase 5 — Integrate Manually Connected Workflows
The current manual transitions should later become integrated flows.

Examples:
- selected sender domains from screening can be sent into infrastructure/domain registry,
- recipient selections can be attached directly to campaigns,
- tracking IDs can be generated from shared campaign recipient data,
- accounting imports can be linked directly to known jobs and campaigns,
- sending surfaces can consume infrastructure entities directly without copy/paste.

---

## Phase 6 — Rebuild the Send Module Properly
The send/mailer module will likely need the most careful engineering.

It should eventually support:
- campaign creation,
- multi-server distribution,
- sender/domain orchestration,
- AI-assisted content helpers,
- preflight checks,
- live PMTA monitoring,
- accounting-driven adaptation,
- job control,
- persistent history.

This is likely the biggest future module after the infrastructure core.

---

## Phase 7 — Consolidate Monitoring Surfaces
Monitoring exists in multiple forms today:
- infrastructure readiness,
- PMTA live panel,
- open tracking,
- accounting analytics,
- jobs telemetry.

In the future these should be exposed through a more coherent operator dashboard rather than scattered across separate workflows.

---

## Recommended Starting Point for Future Work

### Best starting point
Start with **architecture and controlled refactoring**, not with a blind big-bang merge.

### First practical technical step
Create a proper project structure and begin extracting one strong module at a time.

### Best first module to anchor on
`script3.py` should likely be the first major anchor because:
- it already owns core infrastructure concepts,
- it has a real operational database,
- it connects to real external systems,
- it represents the strongest system backbone.

### Best UI shell to grow around
`nibiru.py` should likely remain the UI shell direction, but be gradually backed by real modules instead of placeholders.

---

## Proposed Priority Order

1. Formal architecture report and shared data concepts.
2. Refactor `script3.py` into reusable infrastructure modules.
3. Turn `nibiru.py` into a cleaner shell that consumes real services.
4. Rebuild the send module using the current `script4.html`/`nibiru.py` send UI as the product spec.
5. Centralize tracking-ID logic shared by mailer and tracker.
6. Integrate recipient preparation into a persistent campaign workflow.
7. Integrate post-send analytics and tracking into the campaign/job model.
8. Reduce manual copy/paste transitions progressively.

---

## Important Strategic Decisions to Make Later

These decisions do not need to be finalized immediately, but they will matter:

1. Should there be one central DB or module-specific DBs with links?
2. Which parts stay local-only and which parts become more automated?
3. Which checks remain duplicated intentionally for safety?
4. How much of the current operator manual workflow should be preserved?
5. What is the final source of truth for campaigns and jobs?

---

## Conclusion

The project already contains the main pieces of a serious local email operations platform.

Today they exist as several useful, production-motivated tools that evolved independently:
- one for screening sender domains,
- one for preparing recipient lists,
- one for infrastructure and DNS automation,
- one for campaign sending orchestration,
- one for open tracking,
- one for accounting analytics,
- plus an early shell trying to unify the operator experience.

The correct next move is not reckless immediate merging.
The correct next move is to:

1. document the real purpose of each tool,
2. freeze an architecture target,
3. refactor shared logic deliberately,
4. integrate module by module,
5. preserve what already works operationally while removing duplication gradually.

This report is intended to serve as the baseline planning reference for that future work.
