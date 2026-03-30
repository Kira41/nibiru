# script3.py - Infrastructure Control Plane

## Overview

`script3.py` is the core infrastructure control and automation hub. It manages domains, servers, IPs, DNS records, Namecheap interactions, DKIM generation, PowerMTA configuration generation, and readiness checks.

**File size:** ~294KB
**Role:** Core infrastructure backbone and automation engine.

---

## Dependencies

- **Flask** - Web framework
- **paramiko** - SSH/SFTP connections
- **cryptography** - RSA key generation for DKIM
- **nibiru** - `database_path`
- **tools.domain_bridge** - `init_polling_db`, `list_spamhaus_queue`, `mark_queue_domains_consumed`

---

## Flask Routes

| Route | Method | Function | Purpose |
|-------|--------|----------|---------|
| `/` | GET | `index()` | Renders infrastructure dashboard HTML |
| `/api/data` | GET | `api_get_data()` | Retrieve all infrastructure data |
| `/api/data` | POST | `api_post_data()` | Save/update infrastructure data |
| `/api/data` | DELETE | `api_delete_data()` | Reset to empty default state |
| `/api/dkim/check-ssh` | POST | `api_check_ssh()` | Test SSH/SFTP connectivity |
| `/api/dkim/generate` | POST | `api_generate_dkim()` | Generate and upload DKIM key pairs |
| `/api/pmta/poll-config` | POST | `api_poll_pmta_config()` | Upload PMTA config to remote server |
| `/api/namecheap/test` | POST | `api_namecheap_test()` | Test Namecheap API and list domains |
| `/api/namecheap/poll-domain` | POST | `api_namecheap_poll_domain()` | Update DNS records on Namecheap |
| `/api/namecheap/verify-domain` | POST | `api_namecheap_verify_domain()` | Verify domain DNS health |
| `/api/spamhaus-queue` | GET | `api_get_spamhaus_queue()` | Get pending Spamhaus queue domains |
| `/api/spamhaus-queue/import` | POST | `api_import_spamhaus_queue()` | Import domains from Spamhaus queue |

---

## Global Configuration

| Variable | Value | Purpose |
|----------|-------|---------|
| `DB_PATH` | `database/script3.db` | SQLite database path |
| `STORAGE_KEY` | `mailInfraDashboardDataV4` | App storage key |
| `REMOTE_BASE_DIR` | `/root` | Remote base for DKIM uploads |
| `PMTA_REMOTE_CONFIG_PATH` | `/etc/pmta/config` | Remote PMTA config path |
| `DOMAIN_RE` | Regex | Domain name validation pattern |
| `SELECTOR_RE` | Regex | DKIM selector validation pattern |

---

## Database Schema

### Table: `app_storage`

| Column | Type | Purpose |
|--------|------|---------|
| `storage_key` | TEXT PRIMARY KEY | Data identifier (`mailInfraDashboardDataV4`) |
| `payload` | TEXT NOT NULL | JSON blob of all infrastructure data |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

All infrastructure data is stored as a single JSON payload under one storage key.

---

## Infrastructure Data Model

### Server Object

```python
{
    "id": str,                    # Unique ID
    "name": str,                  # Display name
    "sshHost": str,               # SSH hostname
    "sshPort": int,               # SSH port
    "sshTimeout": int,            # Connection timeout
    "sshUser": str,               # SSH username
    "sshPass": str,               # SSH password
    "dkimFilename": str,          # Default: "dkim.pem"
    "keySize": int,               # 1024, 2048, or 4096
    "pmtaConfigPolledAt": str,    # ISO timestamp
    "pmtaConfigFingerprint": str, # Config hash
    "pmtaConfigRemotePath": str,  # Remote path
}
```

### IP Object

```python
{
    "id": str,                    # Unique ID
    "serverId": str,              # References server
    "ip": str,                    # IPv4 address
    "ptr": str,                   # Reverse DNS
    "rdns": str,                  # Reverse DNS name
    "country": str,               # Country code
    "status": str,                # Status label
    "notes": str,                 # Operator notes
}
```

### Domain Object

```python
{
    "id": str,                    # Unique ID
    "serverId": str,              # References server
    "ipId": str,                  # References IP
    "domain": str,                # Domain name
    "vmta": str,                  # Virtual MTA name
    "helo": str,                  # HELO hostname
    "ptr": str,                   # Expected PTR
    "spf": str,                   # SPF record value
    "dmarc": str,                 # DMARC record value
    "selector": str,              # DKIM selector
    "pemPath": str,               # Remote key path
    "publicKey": str,             # Base64 DER public key
    "dkimRecordHost": str,        # DNS record hostname
    "dkimRecordValue": str,       # DNS record value
    "verification": dict,         # Verification result
    "manualReadyOverride": bool,  # Force-mark as ready
    "createdAt": str,             # ISO timestamp
    "updatedAt": str,             # ISO timestamp
}
```

### Domain Registry Object

```python
{
    "id": str,                    # Unique ID
    "domain": str,                # Domain name
    "provider": str,              # Registrar (e.g., "Namecheap")
    "expiryDate": str,            # YYYY-MM-DD
    "accountUser": str,           # Account username
    "linkedIpId": str,            # References IP
    "note": str,                  # Notes (Spamhaus data, etc.)
}
```

### Namecheap Config

```python
{
    "token": str,                 # ApiUser
    "username": str,              # Username
    "password": str,              # Password
    "apiKey": str,                # API key
    "clientIp": str,              # Whitelisted IP
    "sandbox": bool,              # Use sandbox endpoint
    "monitoredDomains": list,     # Tracked domains
    "lastDomains": list,          # Last API response
    "lastCheckedAt": str,         # ISO timestamp
}
```

### Shiva Bridge Object

```python
{
    "activeServerIds": list,      # Selected server IDs
    "byServerId": {
        "<serverId>": {
            "domainIds": list,
            "smtpHost": str,
            "smtpPort": str,
            "smtpSecurity": str,
            "smtpTimeout": str,
            "smtpUser": str,
            "smtpPass": str,
        }
    },
    "emailUsernames": str,        # Sender email list
    "senderNames": str,           # Sender name list
}
```

---

## Key Classes

### NamecheapClient

Handles Namecheap API communication via XML.

| Method | Purpose |
|--------|---------|
| `_call(command, extra_params)` | HTTP POST to Namecheap API |
| `split_domain(domain)` | Returns (SLD, TLD) tuple |
| `list_domains(page, page_size)` | Paginated domain list |
| `list_all_domains()` | All domains with auto-pagination |
| `list_dns_records(domain)` | Get DNS records from Namecheap |
| `_set_hosts(domain, records)` | Update DNS records |
| `ensure_namecheap_dns(domain)` | Set Namecheap as nameserver |

**Endpoints:** `namecheap.domains.getList`, `namecheap.domains.dns.getHosts`, `namecheap.domains.dns.setHosts`, `namecheap.domains.dns.setDefault`

---

## SSH/SFTP Operations

| Function | Purpose |
|----------|---------|
| `ssh_connect_sftp(host, port, user, password, timeout)` | Establish SSH/SFTP connection via paramiko |
| `sftp_mkdirs(sftp, path)` | Create remote directories recursively |
| `sftp_upload_bytes(sftp, remote_path, data)` | Upload binary data to remote file |

**Authentication:** Password-based via paramiko. AutoAddPolicy for host keys.

---

## DKIM Generation

| Function | Purpose |
|----------|---------|
| `generate_dkim_keypair_local(key_size)` | Generate RSA keypair (PEM + base64 DER) |
| `split_for_dns(value, chunk)` | Split long key for DNS TXT record (200-char chunks) |
| `run_dkim_generation(payload)` | Orchestrate key generation + SFTP upload |

**Upload path:** `/root/{domain}/dkim.pem` (customizable via `dkimFilename`)

**DNS record format:** `v=DKIM1; k=rsa; p={base64_public_key}`

---

## DNS Automation

### Record Types Supported
- A (IPv4 address for domain and HELO)
- MX (mail exchange)
- TXT (SPF, DKIM, DMARC)

### Operations

| Function | Purpose |
|----------|---------|
| `resolve_dns_values(name, record_type)` | Query Google DNS API for public records |
| `build_required_namecheap_records(payload)` | Build all DNS records needed for a domain |
| `poll_namecheap_dns(payload)` | Apply required records to Namecheap |
| `build_domain_verification(payload)` | Compare Namecheap vs public DNS |
| `build_dns_check(...)` | Build individual DNS check result |

### Verification

Compares Namecheap-stored records with public DNS resolution. Reports discrepancies for SPF, DKIM, DMARC, A, and MX records.

---

## PMTA Config Generation

| Function | Purpose |
|----------|---------|
| `run_pmta_config_polling(payload)` | Upload PMTA config to remote server via SFTP |

**Destination:** `/etc/pmta/config`
**Transport:** SFTP binary upload
**Tracking:** Config fingerprint stored for change detection

---

## Frontend Dashboard

The embedded HTML template (~7000+ lines) includes:
- Dark-themed UI with tabs: Overview, PMTA Config, Readiness, DNS, Output, Domains Registry
- Infrastructure tree navigation (Server -> IP -> Domain)
- PowerMTA Config Studio with syntax parsing
- DNS verification with live status checks
- Namecheap domain management panel
- Bulk DKIM generator modal
- Domain registry management with import/export
- Readiness scoring system
- SPF/DKIM/DMARC/PTR verification panels
- JSON data import/export
- Spamhaus queue integration
