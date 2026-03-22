#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

BASE_URL = "https://api.spamhaus.org"
DEFAULT_TIMEOUT = 20
DEFAULT_USER_AGENT = "spamhouse-tool/1.0"


class SpamhausSIAError(Exception):
    pass


class RetryableProviderError(SpamhausSIAError):
    pass


class ProviderUnavailableError(SpamhausSIAError):
    pass


def ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def ts_to_date(ts: Optional[int]) -> str:
    if ts in (None, "", 0):
        return "N/A"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%m/%d/%Y")
    except Exception:
        return "N/A"


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def is_ipv6(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).version == 6
    except ValueError:
        return False


def normalize_domain(value: str) -> str:
    domain = value.strip().lower()
    if not domain:
        raise ValueError("Domain cannot be empty.")
    if domain.startswith("http://") or domain.startswith("https://"):
        raise ValueError("Pass a bare domain only, e.g. example.com (not a URL).")
    if "/" in domain:
        raise ValueError("Pass a bare domain only, not a path/URL.")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def clean_domain(value: str) -> str:
    domain = value.strip().lower()
    if not domain:
        return ""
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.split("/")[0].strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def format_number(value: Any) -> str:
    if value in (None, ""):
        return "N/A"
    try:
        number = float(value)
        if math.isclose(number, round(number), abs_tol=1e-12):
            return str(int(round(number)))
        return f"{number:.4f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def first_present(data: Dict[str, Any], keys: Sequence[str], default: Any = "N/A") -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


class SpamhausSIAClient:
    def __init__(
        self,
        username: str,
        password: str,
        timeout: int = DEFAULT_TIMEOUT,
        label: str = "",
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.username = username
        self.password = password
        self.timeout = timeout
        self.label = label or username
        self.user_agent = user_agent
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.token_expires: int = 0

    def login(self) -> None:
        url = f"{BASE_URL}/api/v1/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "realm": "intel",
        }
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise RetryableProviderError(f"Login temporary failure for {self.label}: {exc}") from exc
        except requests.RequestException as exc:
            raise RetryableProviderError(f"Login request failed for {self.label}: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise SpamhausSIAError(
                f"Login returned non-JSON response for {self.label}: HTTP {response.status_code} {response.text}"
            ) from exc

        if response.status_code in (408, 429, 500, 502, 503, 504):
            raise RetryableProviderError(f"Login temporary HTTP failure for {self.label}: {response.status_code}")

        if response.status_code >= 400:
            raise SpamhausSIAError(
                f"Login failed for {self.label}: HTTP {response.status_code} / body={json.dumps(data, ensure_ascii=False)}"
            )

        if data.get("code") not in (None, 200) or "token" not in data:
            raise SpamhausSIAError(
                f"Login failed for {self.label}: {json.dumps(data, ensure_ascii=False)}"
            )

        self.token = data["token"]
        self.token_expires = int(data.get("expires", 0))

    def ensure_token(self) -> None:
        now = int(time.time())
        if not self.token or now >= (self.token_expires - 120):
            self.login()

    def _headers(self) -> Dict[str, str]:
        self.ensure_token()
        assert self.token
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        allow_404: bool = True,
    ) -> Tuple[int, Any]:
        url = f"{BASE_URL}{path}"
        try:
            response = self.session.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise RetryableProviderError(f"Temporary network failure for {self.label}: {exc}") from exc
        except requests.RequestException as exc:
            raise RetryableProviderError(f"Temporary request failure for {self.label}: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise SpamhausSIAError(
                f"GET {path} returned non-JSON response: HTTP {response.status_code} {response.text}"
            ) from exc

        if allow_404 and response.status_code == 404:
            return 404, data

        if response.status_code in (408, 429, 500, 502, 503, 504):
            raise RetryableProviderError(f"Temporary HTTP {response.status_code} for {self.label}")

        if response.status_code >= 400:
            raise SpamhausSIAError(
                f"GET {path} failed: HTTP {response.status_code} / body={json.dumps(data, ensure_ascii=False)}"
            )

        return response.status_code, data

    def get_json(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        allow_404: bool = True,
    ) -> Any:
        _, data = self._get(path, params=params, allow_404=allow_404)
        return data

    def ip_live_listings(self, ip: str, dataset: str = "ALL", limit: int = 50) -> Dict[str, Any]:
        dataset = dataset.upper()
        if dataset not in {"ALL", "XBL", "CSS", "BCL"}:
            raise ValueError("dataset must be one of: ALL, XBL, CSS, BCL")

        path = f"/api/intel/v1/byobject/cidr/{dataset}/listed/live/{ip}"
        status, data = self._get(path, params={"limit": limit}, allow_404=True)
        if status == 404 or data.get("code") == 404:
            return {"listed": False, "results": [], "raw": data}

        results = data.get("results", []) if isinstance(data, dict) else []
        return {"listed": len(results) > 0, "results": results, "raw": data}

    def ip_history(
        self,
        ip: str,
        dataset: str = "ALL",
        limit: int = 20,
        since: Optional[int] = None,
        until: Optional[int] = None,
    ) -> Dict[str, Any]:
        path = f"/api/intel/v1/byobject/cidr/{dataset.upper()}/listed/history/{ip}"
        params: Dict[str, Any] = {"limit": limit}
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until

        status, data = self._get(path, params=params, allow_404=True)
        if status == 404 or data.get("code") == 404:
            return {"results": [], "raw": data}
        return {"results": data.get("results", []), "raw": data}

    def domain_general(self, domain: str) -> Dict[str, Any]:
        return self.get_json(f"/api/intel/v2/byobject/domain/{domain}", allow_404=True) or {}

    def domain_listing(self, domain: str) -> Dict[str, Any]:
        return self.get_json(f"/api/intel/v2/byobject/domain/{domain}/listing", allow_404=True) or {}

    def domain_dimensions(self, domain: str) -> Dict[str, Any]:
        return self.get_json(f"/api/intel/v2/byobject/domain/{domain}/dimensions", allow_404=True) or {}

    def domain_senders(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/senders", allow_404=True)
        return data if isinstance(data, list) else []

    def domain_nameservers(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/ns", allow_404=True)
        return data if isinstance(data, list) else []

    def domain_a_records(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/a", allow_404=True)
        return data if isinstance(data, list) else []

    def domain_hostnames(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/hostnames", allow_404=True)
        return data if isinstance(data, list) else []

    def check_ip(self, ip: str, dataset: str = "ALL", include_history: bool = False) -> Dict[str, Any]:
        live = self.ip_live_listings(ip, dataset=dataset)
        history = self.ip_history(ip, dataset=dataset, limit=10) if include_history else {"results": []}

        summary = {
            "type": "ip",
            "query": ip,
            "dataset": dataset.upper(),
            "listed": live["listed"],
            "score": None,
            "reasons": [],
            "details": [],
            "history_count": len(history["results"]),
            "raw": {"live": live["raw"], "history": history.get("raw")}
            if include_history
            else {"live": live["raw"]},
        }

        for item in live["results"]:
            reason_parts = []
            for key in ("dataset", "heuristic", "detection", "botname", "rule"):
                value = item.get(key)
                if value not in (None, "", []):
                    reason_parts.append(f"{key}={value}")
            summary["reasons"].append(", ".join(reason_parts) if reason_parts else "listing record present")
            summary["details"].append(
                {
                    "dataset": item.get("dataset"),
                    "ipaddress": item.get("ipaddress"),
                    "listed_ts": item.get("listed"),
                    "listed_iso": ts_to_iso(item.get("listed")),
                    "seen_ts": item.get("seen"),
                    "seen_iso": ts_to_iso(item.get("seen")),
                    "valid_until_ts": item.get("valid_until"),
                    "valid_until_iso": ts_to_iso(item.get("valid_until")),
                    "heuristic": item.get("heuristic"),
                    "detection": item.get("detection"),
                    "botname": item.get("botname"),
                    "rule": item.get("rule"),
                    "asn": item.get("asn"),
                    "cc": item.get("cc"),
                    "protocol": item.get("protocol"),
                    "srcip": item.get("srcip"),
                    "dstip": item.get("dstip"),
                    "srcport": item.get("srcport"),
                    "dstport": item.get("dstport"),
                    "helo": item.get("helo"),
                    "subject": item.get("subject"),
                    "abused": item.get("abused"),
                    "shared": item.get("shared"),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                }
            )
        return summary

    def check_domain(self, domain: str) -> Dict[str, Any]:
        normalized_domain = clean_domain(domain)
        general = self.domain_general(normalized_domain)
        listing = self.domain_listing(normalized_domain)
        dimensions = self.domain_dimensions(normalized_domain)

        try:
            senders = self.domain_senders(normalized_domain)
        except Exception:
            senders = []
        try:
            nameservers = self.domain_nameservers(normalized_domain)
        except Exception:
            nameservers = []
        try:
            a_records = self.domain_a_records(normalized_domain)
        except Exception:
            a_records = []
        try:
            hostnames = self.domain_hostnames(normalized_domain)
        except Exception:
            hostnames = []

        sender_scores = [row.get("score") for row in senders if isinstance(row.get("score"), (int, float))]
        ns_scores = [row.get("score") for row in nameservers if isinstance(row.get("score"), (int, float))]
        a_scores = [row.get("score") for row in a_records if isinstance(row.get("score"), (int, float))]

        listed = bool(listing.get("is-listed", False) or listing.get("is_listed", False))
        reasons: List[str] = []
        if listed:
            reasons.append(f"Domain is currently listed; listed-until={ts_to_iso(listing.get('listed-until'))}")
        tags = general.get("tags", [])
        if tags:
            reasons.append(f"tags={', '.join(tags)}")
        if general.get("abused") is True:
            reasons.append("abused=true")

        return {
            "type": "domain",
            "query": normalized_domain,
            "listed": listed,
            "score": general.get("score"),
            "reasons": reasons,
            "details": {
                "domain": general.get("domain"),
                "last_seen_ts": general.get("last-seen"),
                "last_seen_iso": ts_to_iso(general.get("last-seen")),
                "tags": tags,
                "abused": general.get("abused"),
                "deactivated_ts": general.get("deactivated-ts"),
                "deactivated_iso": ts_to_iso(general.get("deactivated-ts")),
                "whois": general.get("whois", {}),
                "clusters": general.get("clusters", {}),
                "dimensions": dimensions,
                "listing": {
                    "ts": listing.get("ts"),
                    "ts_iso": ts_to_iso(listing.get("ts")),
                    "is_listed": listed,
                    "listed_until": listing.get("listed-until"),
                    "listed_until_iso": ts_to_iso(listing.get("listed-until")),
                },
                "sender_count": len(senders),
                "senders_top10": senders[:10],
                "sender_score_min": min(sender_scores) if sender_scores else None,
                "sender_score_max": max(sender_scores) if sender_scores else None,
                "ns_count": len(nameservers),
                "ns_top10": nameservers[:10],
                "ns_score_min": min(ns_scores) if ns_scores else None,
                "ns_score_max": max(ns_scores) if ns_scores else None,
                "a_count": len(a_records),
                "a_top10": a_records[:10],
                "a_score_min": min(a_scores) if a_scores else None,
                "a_score_max": max(a_scores) if a_scores else None,
                "hostnames_count": len(hostnames),
                "hostnames_top10": hostnames[:10],
            },
            "raw": {
                "general": general,
                "listing": listing,
                "dimensions": dimensions,
                "senders": senders,
                "ns": nameservers,
                "a": a_records,
                "hostnames": hostnames,
            },
        }


class SpamhausAccountRotator:
    def __init__(
        self,
        accounts: Sequence[Dict[str, str]],
        max_requests_per_account: int,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not accounts:
            raise ValueError("At least one account is required")
        self.max_requests_per_account = max_requests_per_account
        self.current_index = 0
        self.lock = threading.Lock()
        self.clients: List[Dict[str, Any]] = []
        for index, account in enumerate(accounts, start=1):
            client = SpamhausSIAClient(
                username=account["username"],
                password=account["password"],
                label=account.get("label") or f"Account {index}",
                timeout=timeout,
            )
            self.clients.append(
                {
                    "client": client,
                    "label": client.label,
                    "used": 0,
                    "cycle_used": 0,
                    "cooldown": False,
                }
            )

    def _reset_cycle_if_needed(self) -> None:
        if all(entry["cycle_used"] >= self.max_requests_per_account or entry["cooldown"] for entry in self.clients):
            for entry in self.clients:
                entry["cycle_used"] = 0
                entry["cooldown"] = False

    def _next_available_index(self) -> int:
        self._reset_cycle_if_needed()
        for offset in range(len(self.clients)):
            idx = (self.current_index + offset) % len(self.clients)
            entry = self.clients[idx]
            if not entry["cooldown"] and entry["cycle_used"] < self.max_requests_per_account:
                return idx
        self._reset_cycle_if_needed()
        for offset in range(len(self.clients)):
            idx = (self.current_index + offset) % len(self.clients)
            entry = self.clients[idx]
            if not entry["cooldown"] and entry["cycle_used"] < self.max_requests_per_account:
                return idx
        raise ProviderUnavailableError("All configured accounts are temporarily unavailable")

    def _reserve_client(self) -> Dict[str, Any]:
        idx = self._next_available_index()
        entry = self.clients[idx]
        entry["used"] += 1
        entry["cycle_used"] += 1
        if entry["cycle_used"] >= self.max_requests_per_account:
            self.current_index = (idx + 1) % len(self.clients)
        else:
            self.current_index = idx
        return entry

    def get_json(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        allow_404: bool = True,
    ) -> Any:
        with self.lock:
            entry = self._reserve_client()
            client: SpamhausSIAClient = entry["client"]
        try:
            return client.get_json(path, params=params, allow_404=allow_404)
        except RetryableProviderError as exc:
            if "429" in str(exc):
                with self.lock:
                    entry["cooldown"] = True
                    self.current_index = (self.current_index + 1) % len(self.clients)
            raise

    def get_usage_snapshot(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [
                {
                    "label": entry["label"],
                    "used": entry["used"],
                    "cycle_used": entry["cycle_used"],
                    "remaining": max(0, self.max_requests_per_account - entry["cycle_used"]),
                    "cooldown": entry["cooldown"],
                }
                for entry in self.clients
            ]

    def get_domain_general(self, domain: str) -> Dict[str, Any]:
        return self.get_json(f"/api/intel/v2/byobject/domain/{domain}", allow_404=True) or {}

    def get_domain_dimensions(self, domain: str) -> Dict[str, Any]:
        return self.get_json(f"/api/intel/v2/byobject/domain/{domain}/dimensions", allow_404=True) or {}

    def get_domain_listing(self, domain: str) -> Dict[str, Any]:
        return self.get_json(f"/api/intel/v2/byobject/domain/{domain}/listing", allow_404=True) or {}

    def get_domain_senders(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/senders", allow_404=True)
        return data if isinstance(data, list) else []

    def get_domain_nameservers(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/ns", allow_404=True)
        return data if isinstance(data, list) else []

    def get_domain_a_records(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/a", allow_404=True)
        return data if isinstance(data, list) else []

    def get_domain_hostnames(self, domain: str) -> List[Dict[str, Any]]:
        data = self.get_json(f"/api/intel/v2/byobject/domain/{domain}/hostnames", allow_404=True)
        return data if isinstance(data, list) else []


AccountRotator = SpamhausAccountRotator


def build_domain_reputation_result(
    domain: str,
    general: Dict[str, Any],
    dimensions: Dict[str, Any],
    listing: Dict[str, Any],
) -> Dict[str, Any]:
    whois = general.get("whois", {}) if isinstance(general.get("whois"), dict) else {}

    human = first_present(dimensions, ["human", "human_score", "humanScore"])
    identity = first_present(dimensions, ["identity", "identity_score", "identityScore"])
    infra = first_present(dimensions, ["infra", "infra_score", "infraScore"])
    malware = first_present(dimensions, ["malware", "malware_score", "malwareScore"])
    smtp = first_present(dimensions, ["smtp", "smtp_score", "smtpScore"])

    score = first_present(general, ["score", "reputation", "reputation_score"])
    registrar = first_present(whois, ["registrar", "registrarName"], "N/A")
    created = ts_to_date(first_present(whois, ["created", "created_ts", "creation_date"], None))
    expires = ts_to_date(first_present(whois, ["expires", "expiration", "expiration_date"], None))

    listed_value = first_present(listing, ["is-listed", "is_listed", "listed"], "N/A")
    listed_until = ts_to_date(first_present(listing, ["listed-until", "listed_until", "listedUntil"], None))

    return {
        "domain": domain,
        "domain_created": created,
        "expiration_date": expires,
        "registrar": registrar,
        "reputation_score": format_number(score),
        "reputation_score_raw": score,
        "human": format_number(human),
        "identity": format_number(identity),
        "infra": format_number(infra),
        "malware": format_number(malware),
        "smtp": format_number(smtp),
        "is_listed": listed_value,
        "listed_until": listed_until,
        "status": "ok",
        "error": "",
        "cached": False,
    }


def make_empty_domain_result(domain: str, status: str, error: str) -> Dict[str, Any]:
    return {
        "domain": domain,
        "domain_created": "N/A",
        "expiration_date": "N/A",
        "registrar": "N/A",
        "reputation_score": "N/A",
        "reputation_score_raw": None,
        "human": "N/A",
        "identity": "N/A",
        "infra": "N/A",
        "malware": "N/A",
        "smtp": "N/A",
        "is_listed": "N/A",
        "listed_until": "N/A",
        "status": status,
        "error": error,
        "cached": False,
    }


def print_human_summary(result: Dict[str, Any]) -> None:
    print("=" * 80)
    print(f"Query   : {result.get('query')}")
    print(f"Type    : {result.get('type')}")
    print(f"Listed  : {result.get('listed')}")
    print(f"Score   : {result.get('score')}")
    print("-" * 80)

    reasons = result.get("reasons") or []
    if reasons:
        print("Reasons:")
        for reason in reasons:
            print(f"  - {reason}")

    print("-" * 80)

    if result.get("type") == "ip":
        details = result.get("details", [])
        if not details:
            print("No active live listings found.")
        else:
            print(f"Active listing records: {len(details)}")
            for index, item in enumerate(details, start=1):
                print(f"\n[{index}] dataset={item.get('dataset')} ip={item.get('ipaddress')}")
                print(f"    listed      : {item.get('listed_iso')}")
                print(f"    valid_until : {item.get('valid_until_iso')}")
                print(f"    heuristic   : {item.get('heuristic')}")
                print(f"    detection   : {item.get('detection')}")
                print(f"    botname     : {item.get('botname')}")
                print(f"    rule        : {item.get('rule')}")
                print(f"    asn/cc      : {item.get('asn')} / {item.get('cc')}")
                print(f"    protocol    : {item.get('protocol')}")
                print(
                    f"    src/dst     : {item.get('srcip')}:{item.get('srcport')} -> {item.get('dstip')}:{item.get('dstport')}"
                )
                print(f"    helo        : {item.get('helo')}")
                if item.get("subject"):
                    print(f"    subject     : {item.get('subject')}")
                if item.get("abused") is not None:
                    print(f"    abused      : {item.get('abused')}")
                if item.get("shared") is not None:
                    print(f"    shared      : {item.get('shared')}")

    elif result.get("type") == "domain":
        details = result.get("details", {})
        print(f"Last seen      : {details.get('last_seen_iso')}")
        print(f"Tags           : {', '.join(details.get('tags', [])) or '-'}")
        print(f"Abused         : {details.get('abused')}")
        print(f"Deactivated    : {details.get('deactivated_iso')}")
        print(f"WHOIS          : {json.dumps(details.get('whois', {}), ensure_ascii=False)}")
        print(f"Clusters       : {json.dumps(details.get('clusters', {}), ensure_ascii=False)}")
        print(f"Dimensions     : {json.dumps(details.get('dimensions', {}), ensure_ascii=False)}")
        print(f"Listing ts     : {details.get('listing', {}).get('ts_iso')}")
        print(f"Listed until   : {details.get('listing', {}).get('listed_until_iso')}")
        print(
            "Senders        : "
            f"{details.get('sender_count')} (score min/max: {details.get('sender_score_min')} / {details.get('sender_score_max')})"
        )
        print(
            "Nameservers    : "
            f"{details.get('ns_count')} (score min/max: {details.get('ns_score_min')} / {details.get('ns_score_max')})"
        )
        print(
            "A records      : "
            f"{details.get('a_count')} (score min/max: {details.get('a_score_min')} / {details.get('a_score_max')})"
        )
        print(f"Hostnames      : {details.get('hostnames_count')}")

    print("=" * 80)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spamhaus Intelligence API checker for IPs and domains")
    parser.add_argument("target", help="IP address or bare domain (example.com)")
    parser.add_argument("--username", required=True, help="Spamhaus SIA username/email")
    parser.add_argument("--password", required=True, help="Spamhaus SIA password")
    parser.add_argument(
        "--dataset",
        default="ALL",
        choices=["ALL", "XBL", "CSS", "BCL"],
        help="Dataset for IP lookups",
    )
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Also query recent IP history (IP mode only)",
    )
    parser.add_argument("--json", action="store_true", help="Print final normalized JSON result")
    parser.add_argument("--raw-json", action="store_true", help="Print raw API payloads too")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    client = SpamhausSIAClient(username=args.username, password=args.password)
    target = args.target.strip()

    try:
        if is_ip(target):
            result = client.check_ip(target, dataset=args.dataset, include_history=args.include_history)
        else:
            result = client.check_domain(normalize_domain(target))

        print_human_summary(result)

        if args.json:
            output = dict(result)
            if not args.raw_json:
                output.pop("raw", None)
            print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
