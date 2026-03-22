#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

import requests

GOOGLE_SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
GOOGLE_WEB_RISK_URL = "https://webrisk.googleapis.com/v1/uris:search"
MICROLINK_URL = "https://api.microlink.io/"

USER_AGENT = "URLReputationChecker/1.0 (+personal-use)"
TIMEOUT = 20

SAFE_BROWSING_THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]

SAFE_BROWSING_PLATFORM_TYPES = ["ANY_PLATFORM"]
SAFE_BROWSING_ENTRY_TYPES = ["URL"]

WEB_RISK_THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
]


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = "https://" + raw
    return raw


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


class URLReputationChecker:
    def __init__(self, safe_browsing_api_key: str | None = None, web_risk_api_key: str | None = None):
        self.safe_browsing_api_key = safe_browsing_api_key or os.getenv("GOOGLE_SAFE_BROWSING_API_KEY", "").strip()
        self.web_risk_api_key = web_risk_api_key or os.getenv("GOOGLE_WEB_RISK_API_KEY", "").strip()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_metadata(self, url: str) -> dict:
        try:
            response = self.session.get(MICROLINK_URL, params={"url": url}, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.json()
            data = body.get("data", {})
            return {
                "ok": True,
                "title": data.get("title") or "",
                "description": data.get("description") or "",
                "publisher": data.get("publisher") or "",
                "lang": data.get("lang") or "",
                "author": data.get("author") or "",
                "logo": data.get("logo", {}).get("url") if isinstance(data.get("logo"), dict) else "",
                "image": data.get("image", {}).get("url") if isinstance(data.get("image"), dict) else "",
                "url": data.get("url") or url,
                "status_code": response.status_code,
                "note": "",
            }
        except Exception as exc:
            return {
                "ok": False,
                "title": "",
                "description": "",
                "publisher": "",
                "lang": "",
                "author": "",
                "logo": "",
                "image": "",
                "url": url,
                "status_code": None,
                "note": str(exc),
            }

    def check_google_safe_browsing(self, url: str) -> dict:
        if not self.safe_browsing_api_key:
            return {
                "enabled": False,
                "provider": "google_safe_browsing",
                "blacklisted": None,
                "matches": [],
                "error": "Missing GOOGLE_SAFE_BROWSING_API_KEY",
            }

        endpoint = f"{GOOGLE_SAFE_BROWSING_URL}?key={self.safe_browsing_api_key}"
        payload = {
            "client": {
                "clientId": "personal-url-checker",
                "clientVersion": "1.0",
            },
            "threatInfo": {
                "threatTypes": SAFE_BROWSING_THREAT_TYPES,
                "platformTypes": SAFE_BROWSING_PLATFORM_TYPES,
                "threatEntryTypes": SAFE_BROWSING_ENTRY_TYPES,
                "threatEntries": [{"url": url}],
            },
        }

        try:
            response = self.session.post(endpoint, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json() if response.content else {}
            matches = data.get("matches", []) or []
            parsed_matches = []
            for match in matches:
                parsed_matches.append(
                    {
                        "threatType": match.get("threatType", ""),
                        "platformType": match.get("platformType", ""),
                        "threatEntryType": match.get("threatEntryType", ""),
                        "cacheDuration": match.get("cacheDuration", ""),
                        "threat": match.get("threat", {}),
                    }
                )
            return {
                "enabled": True,
                "provider": "google_safe_browsing",
                "blacklisted": bool(parsed_matches),
                "matches": parsed_matches,
                "error": "",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "provider": "google_safe_browsing",
                "blacklisted": None,
                "matches": [],
                "error": str(exc),
            }

    def check_google_web_risk(self, url: str) -> dict:
        if not self.web_risk_api_key:
            return {
                "enabled": False,
                "provider": "google_web_risk",
                "blacklisted": None,
                "threat": {},
                "error": "Missing GOOGLE_WEB_RISK_API_KEY",
            }

        params = {
            "key": self.web_risk_api_key,
            "uri": url,
            "threatTypes": WEB_RISK_THREAT_TYPES,
        }

        try:
            response = self.session.get(GOOGLE_WEB_RISK_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json() if response.content else {}
            threat = data.get("threat") or {}
            threat_types = threat.get("threatTypes", []) if isinstance(threat, dict) else []
            expire_time = threat.get("expireTime", "") if isinstance(threat, dict) else ""
            return {
                "enabled": True,
                "provider": "google_web_risk",
                "blacklisted": bool(threat_types),
                "threat": {
                    "threatTypes": threat_types,
                    "expireTime": expire_time,
                },
                "error": "",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "provider": "google_web_risk",
                "blacklisted": None,
                "threat": {},
                "error": str(exc),
            }

    def build_verdict(self, safe_browsing_result: dict, web_risk_result: dict) -> dict:
        provider_hits = []
        provider_errors = []
        provider_clean = []

        for result in [safe_browsing_result, web_risk_result]:
            if result.get("blacklisted") is True:
                provider_hits.append(result["provider"])
            elif result.get("blacklisted") is False:
                provider_clean.append(result["provider"])
            else:
                provider_errors.append(result["provider"])

        if provider_hits:
            return {
                "status": "blacklisted",
                "blacklisted": True,
                "confidence": "high",
                "detected_by": provider_hits,
                "checked_clean_by": provider_clean,
                "unavailable": provider_errors,
            }

        if provider_clean:
            return {
                "status": "clean",
                "blacklisted": False,
                "confidence": "medium" if provider_errors else "high",
                "detected_by": [],
                "checked_clean_by": provider_clean,
                "unavailable": provider_errors,
            }

        return {
            "status": "unknown",
            "blacklisted": None,
            "confidence": "low",
            "detected_by": [],
            "checked_clean_by": [],
            "unavailable": provider_errors,
        }

    def inspect_url(self, raw_url: str) -> dict:
        normalized_url = normalize_url(raw_url)
        if not normalized_url:
            return {"error": "Empty URL"}

        domain = extract_domain(normalized_url)
        if not domain:
            return {"error": "Invalid URL: unable to parse domain", "input": raw_url}

        metadata = self.fetch_metadata(normalized_url)
        safe_browsing_result = self.check_google_safe_browsing(normalized_url)
        web_risk_result = self.check_google_web_risk(normalized_url)
        verdict = self.build_verdict(safe_browsing_result, web_risk_result)

        return {
            "input": raw_url,
            "normalized_url": normalized_url,
            "domain": domain,
            "metadata": metadata,
            "checks": {
                "google_safe_browsing": safe_browsing_result,
                "google_web_risk": web_risk_result,
            },
            "verdict": verdict,
        }


def print_human_readable(result: dict) -> None:
    if result.get("error"):
        print(f"Error: {result['error']}")
        return

    print("=" * 70)
    print(f"URL        : {result['normalized_url']}")
    print(f"Domain     : {result['domain']}")

    metadata = result.get("metadata", {})
    print(f"Title      : {metadata.get('title', '')}")
    print(f"Publisher  : {metadata.get('publisher', '')}")
    print(f"Language   : {metadata.get('lang', '')}")
    print(f"Author     : {metadata.get('author', '')}")
    print(f"Description: {metadata.get('description', '')}")
    print("-" * 70)

    verdict = result.get("verdict", {})
    print(f"Blacklist   : {verdict.get('blacklisted')}")
    print(f"Status      : {verdict.get('status')}")
    print(f"Confidence  : {verdict.get('confidence')}")
    print(f"Detected by : {', '.join(verdict.get('detected_by', [])) or '-'}")
    print(f"Clean by    : {', '.join(verdict.get('checked_clean_by', [])) or '-'}")
    print(f"Unavailable : {', '.join(verdict.get('unavailable', [])) or '-'}")
    print("-" * 70)

    checks = result.get("checks", {})
    for check_name, check_data in checks.items():
        print(f"[{check_name}]")
        print(f"  enabled    : {check_data.get('enabled')}")
        print(f"  blacklisted: {check_data.get('blacklisted')}")
        if check_name == "google_safe_browsing":
            print(f"  matches    : {json.dumps(check_data.get('matches', []), ensure_ascii=False)}")
        else:
            print(f"  threat     : {json.dumps(check_data.get('threat', {}), ensure_ascii=False)}")
        print(f"  error      : {check_data.get('error', '')}")
        print("-" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Check a URL and return metadata plus blacklist status using "
            "Google Safe Browsing and optional Google Web Risk."
        )
    )
    parser.add_argument("url", help="URL to inspect")
    parser.add_argument("--safe-browsing-key", default="", help="Google Safe Browsing API key")
    parser.add_argument("--web-risk-key", default="", help="Google Web Risk API key (optional)")
    parser.add_argument("--json", action="store_true", help="Print raw JSON output")
    args = parser.parse_args()

    checker = URLReputationChecker(
        safe_browsing_api_key=args.safe_browsing_key,
        web_risk_api_key=args.web_risk_key,
    )
    result = checker.inspect_url(args.url)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human_readable(result)

    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
