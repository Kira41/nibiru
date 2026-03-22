#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from typing import Any

DEFAULT_TIMEOUT = 4.0
DNS_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA"]
DIG_STATUS_PATTERN = re.compile(r"status:\s*([A-Z]+)")


def normalize_domain(domain: str) -> str:
    value = domain.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0]
    value = value.strip(".")
    return value


def is_domain_syntax_valid(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False

    labels = domain.split(".")
    if len(labels) < 2:
        return False

    label_pattern = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
    return all(label_pattern.match(label) for label in labels)


class DNSShaker:
    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def _clean_record_text(self, record_type: str, value: str) -> str:
        cleaned = value.strip().strip('"')
        if record_type in {"NS", "CNAME", "SOA", "MX"}:
            cleaned = cleaned.rstrip(".")
        return cleaned

    def _dig_status(self, domain: str, record_type: str) -> str | None:
        command = ["dig", "+noedns", domain, record_type]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout + 1,
                check=False,
            )
        except Exception:
            return None

        combined = f"{completed.stdout}\n{completed.stderr}"
        match = DIG_STATUS_PATTERN.search(combined)
        return match.group(1) if match else None

    def query_record(self, domain: str, record_type: str) -> dict[str, Any]:
        command = [
            "dig",
            "+time=2",
            "+tries=1",
            "+short",
            domain,
            record_type,
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout + 1,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "type": record_type,
                "valid": False,
                "status": "invalid",
                "records": [],
                "error": "DNS query timed out",
                "command": shlex.join(command),
            }
        except FileNotFoundError:
            return {
                "type": record_type,
                "valid": False,
                "status": "invalid",
                "records": [],
                "error": "dig command is not installed",
                "command": shlex.join(command),
            }

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        records = [self._clean_record_text(record_type, line) for line in stdout.splitlines() if line.strip()]

        if records:
            return {
                "type": record_type,
                "valid": True,
                "status": "valid",
                "records": records,
                "error": None,
                "command": shlex.join(command),
            }

        dig_status = self._dig_status(domain, record_type)
        if dig_status and dig_status != "NOERROR":
            error_message = f"Resolver returned DNS status {dig_status}"
        elif completed.returncode != 0:
            error_message = stderr or f"dig exited with code {completed.returncode}"
        else:
            error_message = "No answer returned"

        return {
            "type": record_type,
            "valid": False,
            "status": "invalid",
            "records": [],
            "error": error_message,
            "command": shlex.join(command),
        }

    def audit_domain(self, raw_domain: str) -> dict[str, Any]:
        domain = normalize_domain(raw_domain)
        syntax_valid = is_domain_syntax_valid(domain)

        result: dict[str, Any] = {
            "input": raw_domain,
            "domain": domain,
            "checked_at_unix": int(time.time()),
            "syntax_valid": syntax_valid,
            "status": "invalid",
            "records": {},
            "summary": {
                "valid_record_types": 0,
                "invalid_record_types": 0,
                "notes": [],
            },
        }

        if not syntax_valid:
            result["summary"]["notes"].append("Domain syntax is invalid")
            return result

        for record_type in DNS_RECORD_TYPES:
            record_result = self.query_record(domain, record_type)
            result["records"][record_type] = record_result
            if record_result["valid"]:
                result["summary"]["valid_record_types"] += 1
            else:
                result["summary"]["invalid_record_types"] += 1

        if result["records"]["NS"]["valid"] and result["records"]["SOA"]["valid"]:
            result["status"] = "valid"
        elif result["summary"]["valid_record_types"] > 0:
            result["status"] = "partial"
            result["summary"]["notes"].append("Some DNS records were found, but required authority records are incomplete")
        else:
            result["summary"]["notes"].append("No DNS records were found for the checked record types")

        if not result["records"]["A"]["valid"] and not result["records"]["AAAA"]["valid"] and not result["records"]["CNAME"]["valid"]:
            result["summary"]["notes"].append("No A, AAAA, or CNAME record was found for the apex domain")

        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DNS Shaker: inspect a domain and report DNS record values with valid/invalid status"
    )
    parser.add_argument("domain", help="Bare domain or URL, for example: example.com")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="DNS timeout in seconds")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    checker = DNSShaker(timeout=args.timeout)
    result = checker.audit_domain(args.domain)

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))

    if result["status"] == "invalid":
        sys.exit(1)


if __name__ == "__main__":
    main()
