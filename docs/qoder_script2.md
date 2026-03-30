# script2.py - Recipient Email Extractor & Grouping Tool

## Overview

`script2.py` is the recipient list preparation tool. It extracts emails from raw text, groups them by domain using multiple algorithms, and provides filtering, selection, and export capabilities. Results can be persisted as extraction run snapshots.

**File size:** ~85KB
**Role:** Recipient-side list preparation tool.

---

## Dependencies

- **Flask** - Web framework
- **nibiru** - `database_path`

---

## Flask Routes

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/` | GET | `index()` | Renders main HTML UI |
| `/api/settings` | GET | `api_get_settings()` | Retrieve saved settings |
| `/api/settings` | POST | `api_save_settings()` | Save settings |
| `/api/settings` | DELETE | `api_delete_settings()` | Delete settings |
| `/api/extraction-runs` | GET | `api_list_extraction_runs()` | List runs (limit param, default 25, max 100) |
| `/api/extraction-runs` | POST | `api_save_extraction_run()` | Save extraction run snapshot |
| `/api/extraction-runs/<id>` | GET | `api_get_extraction_run()` | Load specific run |
| `/api/extraction-runs/<id>` | DELETE | `api_delete_extraction_run()` | Delete specific run |

---

## Database Schema

### Table: `app_storage`

| Column | Type | Purpose |
|--------|------|---------|
| `storage_key` | TEXT PRIMARY KEY | Settings identifier |
| `payload` | TEXT NOT NULL | JSON settings data |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

### Table: `extraction_runs`

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-increment ID |
| `label` | TEXT NOT NULL | Human-readable label |
| `payload` | TEXT NOT NULL | Full JSON snapshot |
| `total_emails` | INTEGER | Raw email count |
| `unique_emails` | INTEGER | Deduplicated count |
| `group_count` | INTEGER | Number of groups |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

---

## Email Extraction

1. **Regex matching:** Finds all emails via `/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g`
2. **Normalization:** Lowercased for case-insensitive dedup
3. **Deduplication:** Tracks seen emails, separates duplicates
4. **Invalid detection:** Identifies non-email tokens in input

---

## Grouping Algorithms

10 distinct grouping methods available:

| Method | Description |
|--------|-------------|
| `exact` | Group by exact domain name (no merging) |
| `smart` | Similarity-based using Levenshtein distance with configurable threshold |
| `provider-alias` | Groups by provider defaults (hotmail/outlook/live -> Microsoft) |
| `strict-alias` | Only groups if alias match exists, otherwise exact domain |
| `root-provider` | Groups by root provider domain (handles subdomains) |
| `subdomain-merge` | Merges all subdomains to root domain |
| `normalize-domain` | Groups by normalized domain name |
| `manual-rules` | User-defined rules (format: `domain1, domain2 => groupname`) |
| `company-family` | Groups by company family key (alphanumeric core) |
| `hybrid` | Combines manual rules + provider aliases + smart grouping |

### Provider Aliases

```
gmail/googlemail -> Google
hotmail/outlook/live/msn -> Microsoft
yahoo/ymail/rocketmail -> Yahoo
icloud/me/mac -> Apple
proton/protonmail -> Proton
aol -> AOL
yandex -> Yandex
zoho -> Zoho
gmx -> GMX
```

### Smart Grouping Algorithm

Uses Levenshtein distance for domain similarity scoring:
- Calculates edit distance between domain cores
- Similarity score = 1 - (distance / max_length), with +0.15 bonus for substring matches
- Groups domains exceeding threshold into same family
- Best family key chosen via majority voting + length heuristics

### Small Group Collection

Groups with fewer emails than `collectLimit` are batched into combined cards with aggregated labels.

---

## Settings Persistence

Settings stored in both browser localStorage and SQLite database.

### Settings Object

```python
{
    "groupCategory": str,         # "basic"
    "groupMethod": str,           # "smart"
    "similarityThreshold": str,   # "0.7"
    "manualRulesInput": str,
    "collectSmallMode": bool,
    "collectLimit": str,          # "100"
    "searchInput": str,
    "minEmailsFilter": str,
    "maxEmailsFilter": str,
    "providerFilter": str,        # "all"
    "showOnlySelectedMode": bool,
    "showOnlyPinnedMode": bool,
    "compactViewMode": bool,
    "rememberSettingsMode": bool,
    "sortMode": str,              # "count-desc"
}
```

---

## Export Options

- **Copy Emails by Group** - clipboard copy of all emails in a group
- **Copy Group Name** - clipboard copy of group name
- **Copy Selected Groups** - all emails from selected groups, formatted with headers
- **Copy Duplicates** - all duplicate emails found
- **Copy Invalid Entries** - non-email tokens
- **Snapshot Export** - full extraction snapshot saved to database

### Snapshot Structure

```python
{
    "label": str,              # "Attempt N - X emails"
    "version": 1,
    "inputText": str,
    "settings": dict,
    "summary": {
        "totalEmails": int,
        "uniqueEmails": int,
        "duplicatesRemoved": int,
        "invalidEntries": int,
        "mergedDomains": int,
        "collectedCards": int,
        "visibleGroups": int,
        "groupCount": int,
    },
    "extraction": {
        "rawEmails": list,
        "uniqueEmails": list,
        "duplicates": list,
        "invalidEntries": list,
        "grouped": dict,
        "selected": list,
        "pinned": list,
        "sortMode": str,
    },
}
```

---

## Frontend Features

- Domain cards with checkboxes, copy buttons, pin buttons
- Selection helpers: select all visible, top N, pinned only
- Search and filter (min/max email count, provider, selection, pinned)
- Sort modes: count-desc, count-asc, name-asc, name-desc (pinned always first)
- Compact view mode (hides email textareas)
- Extraction history sidebar with load/delete
- Summary statistics panel
- Top groups sidebar
- Demo sample data
