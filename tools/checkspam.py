import json
import subprocess
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from spamassassin_client import SpamAssassin

    HAS_SPAMASSASSIN_CLIENT = True
except Exception:
    HAS_SPAMASSASSIN_CLIENT = False


POSTMARK_URL = "https://spamcheck.postmarkapp.com/filter"
RSPAMD_URL = "http://localhost:11333/checkv2"
DEFAULT_TIMEOUT = 30


def build_raw_email(
    subject: str,
    body: str,
    from_addr: str = "sender@example.com",
    to_addr: str = "recipient@example.com",
    content_type: str = "plain",
    extra_headers: Optional[Dict[str, str]] = None,
) -> bytes:
    """
    Build a raw RFC5322 email because these engines expect the full raw
    message, not just isolated body text.
    """
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject

    if extra_headers:
        for key, value in extra_headers.items():
            msg[key] = value

    if content_type == "html":
        msg.set_content("This message contains HTML content.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    return msg.as_bytes()


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return default


def clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def normalize_spamassassin_like(
    score: Optional[float], threshold: float = 5.0
) -> Optional[float]:
    """
    Convert a SpamAssassin-like score to normalized [0..1].
    Heuristic:
      0        -> 0.0
      threshold-> ~0.67
      1.5x thr -> ~1.0
    """
    if score is None:
        return None
    if score <= 0:
        return 0.0
    normalized = score / (threshold * 1.5)
    return clamp(normalized, 0.0, 1.0)


def normalize_rspamd(
    score: Optional[float], required_score: Optional[float]
) -> Optional[float]:
    """Convert an Rspamd score to normalized [0..1]."""
    if score is None:
        return None
    if required_score is None or required_score <= 0:
        required_score = 7.0
    if score <= 0:
        return 0.0
    normalized = score / (required_score * 1.5)
    return clamp(normalized, 0.0, 1.0)


def weighted_average(items: List[Tuple[Optional[float], float]]) -> Optional[float]:
    """Compute a weighted average from (value, weight) pairs."""
    valid = [(value, weight) for value, weight in items if value is not None and weight > 0]
    if not valid:
        return None
    total_weight = sum(weight for _, weight in valid)
    if total_weight == 0:
        return None
    return sum(value * weight for value, weight in valid) / total_weight


def verdict_from_score(score_0_100: float) -> str:
    if score_0_100 >= 80:
        return "likely_spam"
    if score_0_100 >= 60:
        return "suspicious"
    if score_0_100 >= 40:
        return "borderline"
    return "likely_ham"


def check_with_postmark(
    raw_email: bytes, timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Postmark accepts a raw email and can return score / rules / report.
    """
    try:
        payload = {
            "email": raw_email.decode("utf-8", errors="replace"),
            "options": "long",
        }
        response = requests.post(
            POSTMARK_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "engine": "postmark_spamcheck",
            "ok": bool(data.get("success", False)),
            "score": safe_float(data.get("score")),
            "threshold": 5.0,
            "rules": data.get("rules", []),
            "report": data.get("report"),
            "raw": data,
            "error": None,
        }
    except Exception as exc:
        return {
            "engine": "postmark_spamcheck",
            "ok": False,
            "score": None,
            "threshold": 5.0,
            "rules": [],
            "report": None,
            "raw": None,
            "error": str(exc),
        }


def check_with_spamassassin_client(raw_email: bytes) -> Dict[str, Any]:
    """
    Requires:
      pip install spamassassin-client
      and spamd running locally
    """
    if not HAS_SPAMASSASSIN_CLIENT:
        return {
            "engine": "spamassassin_client",
            "ok": False,
            "score": None,
            "threshold": 5.0,
            "rules": [],
            "report": None,
            "raw": None,
            "error": "spamassassin_client is not installed",
        }

    try:
        assassin = SpamAssassin(raw_email)
        score = safe_float(assassin.get_score())
        report_json = None
        try:
            report_json = assassin.get_report_json()
        except Exception:
            report_json = None

        return {
            "engine": "spamassassin_client",
            "ok": True,
            "score": score,
            "threshold": 5.0,
            "rules": report_json.get("tests", []) if isinstance(report_json, dict) else [],
            "report": report_json,
            "raw": report_json,
            "error": None,
        }
    except Exception as exc:
        return {
            "engine": "spamassassin_client",
            "ok": False,
            "score": None,
            "threshold": 5.0,
            "rules": [],
            "report": None,
            "raw": None,
            "error": str(exc),
        }


def check_with_spamc(
    raw_email: bytes,
    spamc_bin: str = "spamc",
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Use the spamc CLI as a fallback.
    Example useful mode:
      spamc -R
    The first line is expected to contain score/threshold.
    """
    try:
        proc = subprocess.run(
            [spamc_bin, "-R"],
            input=raw_email,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")

        score = None
        threshold = 5.0

        lines = stdout.splitlines()
        first_line = lines[0].strip() if lines else ""
        if "/" in first_line:
            left, right = first_line.split("/", 1)
            score = safe_float(left.strip())
            threshold = safe_float(right.strip(), 5.0) or 5.0

        return {
            "engine": "spamc_cli",
            "ok": proc.returncode == 0,
            "score": score,
            "threshold": threshold,
            "rules": [],
            "report": stdout,
            "raw": {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": proc.returncode,
            },
            "error": stderr if proc.returncode != 0 else None,
        }
    except Exception as exc:
        return {
            "engine": "spamc_cli",
            "ok": False,
            "score": None,
            "threshold": 5.0,
            "rules": [],
            "report": None,
            "raw": None,
            "error": str(exc),
        }


def check_with_rspamd(
    raw_email: bytes,
    rspamd_url: str = RSPAMD_URL,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    try:
        response = requests.post(
            rspamd_url,
            data=raw_email,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "engine": "rspamd",
            "ok": True,
            "score": safe_float(data.get("score")),
            "threshold": safe_float(data.get("required_score"), 7.0),
            "action": data.get("action"),
            "symbols": data.get("symbols", {}),
            "urls": data.get("urls", []),
            "raw": data,
            "error": None,
        }
    except Exception as exc:
        return {
            "engine": "rspamd",
            "ok": False,
            "score": None,
            "threshold": 7.0,
            "action": None,
            "symbols": {},
            "urls": [],
            "raw": None,
            "error": str(exc),
        }


def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize all engines to [0..1], then produce a 0..100 final score.
    Local engines are weighted slightly higher than the remote API.
    """
    normalized_items: List[Tuple[Optional[float], float]] = []
    engine_summaries: List[Dict[str, Any]] = []

    for item in results:
        engine = item["engine"]
        ok = item.get("ok", False)
        score = item.get("score")
        threshold = item.get("threshold")

        normalized = None
        weight = 1.0

        if engine in ("postmark_spamcheck", "spamassassin_client", "spamc_cli"):
            normalized = normalize_spamassassin_like(score, threshold or 5.0)
        elif engine == "rspamd":
            normalized = normalize_rspamd(score, threshold)

        if engine == "postmark_spamcheck":
            weight = 0.9
        elif engine in ("spamassassin_client", "spamc_cli"):
            weight = 1.1
        elif engine == "rspamd":
            weight = 1.2

        if not ok:
            normalized = None

        normalized_items.append((normalized, weight))
        engine_summaries.append(
            {
                "engine": engine,
                "ok": ok,
                "score_raw": score,
                "threshold_raw": threshold,
                "normalized_0_1": normalized,
                "error": item.get("error"),
            }
        )

    consensus_0_1 = weighted_average(normalized_items)
    if consensus_0_1 is None:
        final_score = 0.0
        confidence = 0.0
    else:
        final_score = round(consensus_0_1 * 100, 2)

        ok_count = sum(1 for result in results if result.get("ok"))
        available_count = len(results)
        agreement_bonus = 0.0

        valid_norms = [value for value, _ in normalized_items if value is not None]
        if len(valid_norms) >= 2:
            spread = max(valid_norms) - min(valid_norms)
            agreement_bonus = clamp(1.0 - spread, 0.0, 1.0) * 20.0

        base_conf = (ok_count / max(available_count, 1)) * 80.0
        confidence = round(clamp(base_conf + agreement_bonus, 0.0, 100.0), 2)

    verdict = verdict_from_score(final_score)

    return {
        "final_score_0_100": final_score,
        "verdict": verdict,
        "confidence_0_100": confidence,
        "engines": engine_summaries,
    }


def analyze_email_consensus(
    subject: str,
    body: str,
    from_addr: str = "sender@example.com",
    to_addr: str = "recipient@example.com",
    content_type: str = "plain",
    use_postmark: bool = True,
    use_spamassassin_client: bool = True,
    use_spamc_cli: bool = False,
    use_rspamd: bool = True,
    rspamd_url: str = RSPAMD_URL,
) -> Dict[str, Any]:
    raw_email = build_raw_email(
        subject=subject,
        body=body,
        from_addr=from_addr,
        to_addr=to_addr,
        content_type=content_type,
    )

    results: List[Dict[str, Any]] = []

    if use_postmark:
        results.append(check_with_postmark(raw_email))
    if use_spamassassin_client:
        results.append(check_with_spamassassin_client(raw_email))
    if use_spamc_cli:
        results.append(check_with_spamc(raw_email))
    if use_rspamd:
        results.append(check_with_rspamd(raw_email, rspamd_url=rspamd_url))

    consensus = aggregate_results(results)

    return {
        "input": {
            "subject": subject,
            "body_preview": body[:500],
            "from_addr": from_addr,
            "to_addr": to_addr,
            "content_type": content_type,
        },
        "raw_email_preview": raw_email.decode("utf-8", errors="replace")[:1000],
        "results": results,
        "consensus": consensus,
    }


def build_llm_prompt(analysis_result: Dict[str, Any]) -> str:
    """
    Build a prompt for a second-stage LLM to summarize the technical spam
    outputs without inventing facts.
    """
    compact = {
        "input": analysis_result["input"],
        "consensus": analysis_result["consensus"],
        "results": [],
    }

    for result in analysis_result["results"]:
        item = {
            "engine": result.get("engine"),
            "ok": result.get("ok"),
            "score": result.get("score"),
            "threshold": result.get("threshold"),
            "error": result.get("error"),
        }

        if result.get("engine") == "rspamd":
            item["action"] = result.get("action")
            item["top_symbols"] = dict(list((result.get("symbols") or {}).items())[:10])

        if result.get("engine") in (
            "postmark_spamcheck",
            "spamassassin_client",
            "spamc_cli",
        ):
            item["rules"] = result.get("rules")

        compact["results"].append(item)

    return f"""
You are an email deliverability and anti-spam analyst.

Your task:
1. Read the JSON analysis below.
2. Produce a precise spam-risk assessment for the email.
3. Do NOT invent any rules or facts that are not present in the JSON.
4. Explain disagreements between engines if they exist.
5. Output exactly this JSON schema:

{{
  "final_verdict": "likely_spam | suspicious | borderline | likely_ham",
  "final_score_0_100": number,
  "confidence_0_100": number,
  "short_reason": "1-2 sentence summary",
  "key_signals": ["signal 1", "signal 2", "signal 3"],
  "engine_summary": [
    {{
      "engine": "name",
      "status": "ok | failed",
      "finding": "short summary"
    }}
  ],
  "recommended_action": "deliver | review_manually | reject"
}}

Important rules:
- If consensus final_score_0_100 >= 80 => recommended_action = "reject"
- If consensus final_score_0_100 >= 60 and < 80 => recommended_action = "review_manually"
- Otherwise => recommended_action = "deliver"
- Preserve the exact consensus score and confidence from the JSON if present.

Analysis JSON:
{json.dumps(compact, ensure_ascii=False, indent=2)}
""".strip()


if __name__ == "__main__":
    subject = "Limited time offer - claim your free bonus now"
    body = """
Hello,

You have been selected for a special limited-time reward.
Click the link below now to claim your free bonus instantly.

Best regards
"""

    result = analyze_email_consensus(
        subject=subject,
        body=body,
        from_addr="marketing@example.com",
        to_addr="user@example.com",
        content_type="plain",
        use_postmark=True,
        use_spamassassin_client=True,
        use_spamc_cli=False,
        use_rspamd=True,
    )

    print("=" * 80)
    print("CONSENSUS RESULT")
    print(json.dumps(result["consensus"], ensure_ascii=False, indent=2))

    print("\n" + "=" * 80)
    print("FULL RESULT")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    print("\n" + "=" * 80)
    print("LLM PROMPT")
    print(build_llm_prompt(result))
