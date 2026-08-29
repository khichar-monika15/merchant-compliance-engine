from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from backend.agents._audit import failure
from backend.models.schemas import AuditLogEntry, EngineState, PCIResult
from backend.tools.csp_parser import analyze_security_headers

_PCI_DB_PATH = Path(__file__).parent.parent / "knowledge" / "pci_dss_surface_checks.json"


def _load_pci_db() -> dict:
    with _PCI_DB_PATH.open() as f:
        return json.load(f)


_PCI_DB = _load_pci_db()


def _check(check_id: str) -> dict:
    return next(c for c in _PCI_DB["checks"] if c["id"] == check_id)


_SCRIPT_INVENTORY = _check("PCI-001")
_SRI = _check("PCI-002")["scoring"]
_CSP = _check("PCI-004")["scoring"]
_HEADER_SUITE = _check("PCI-005")["scoring"]

_HEADER_POINTS = {h["name"]: h["points"] for h in _HEADER_SUITE["headers"]}

# PCI-001 deducts by third-party script count; the thresholds live in the condition strings
_SCRIPT_COUNT_TIERS: list[tuple[int, int, str]] = []
for _d in _SCRIPT_INVENTORY["scoring"]["deductions"]:
    _m = re.fullmatch(r"third_party_scripts > (\d+)", _d["condition"])
    if _m:
        _SCRIPT_COUNT_TIERS.append((int(_m.group(1)), _d["points"], _d["reason"]))
_SCRIPT_COUNT_TIERS.sort(reverse=True)


def _score_headers(security_analysis: dict) -> tuple[int, list[str]]:
    """Score CSP (PCI-004) and the security header suite (PCI-005) out of 50."""
    score = _CSP["max_points"] + _HEADER_SUITE["max_points"]
    issues: list[str] = []

    csp = security_analysis.get("csp", {})
    if not csp.get("present"):
        score -= _CSP["no_csp_deduction"]
        issues.append("CSP header missing (PCI 11.6.1)")
    elif csp.get("strength") == "weak":
        score -= _CSP["weak_csp_deduction"]
        issues.append("CSP is present but weak")
    elif csp.get("strength") == "moderate":
        score -= _CSP["moderate_csp_deduction"]

    suite = [
        ("hsts", "Strict-Transport-Security", "HSTS missing — HTTPS not enforced"),
        ("x_frame_options", "X-Frame-Options", "X-Frame-Options missing — clickjacking risk"),
        ("x_content_type", "X-Content-Type-Options", "X-Content-Type-Options: nosniff missing"),
        ("referrer_policy", "Referrer-Policy", "Referrer-Policy missing"),
    ]
    for key, header_name, message in suite:
        if not security_analysis.get(key, {}).get("present"):
            score -= _HEADER_POINTS[header_name]
            issues.append(message)

    return max(0, score), issues


def _score_scripts(third_party_count: int, without_sri: int) -> tuple[int, list[str]]:
    """Score script inventory (PCI-001) and SRI coverage (PCI-002) out of 50."""
    score = _SCRIPT_INVENTORY["scoring"]["max_points"] + _SRI["max_points"]
    issues: list[str] = []

    for threshold, points, reason in _SCRIPT_COUNT_TIERS:
        if third_party_count > threshold:
            score -= points
            issues.append(
                f"{third_party_count} third-party scripts loaded — {reason} "
                f"(PCI {_SCRIPT_INVENTORY['requirement']})"
            )
            break

    if without_sri > 0:
        score -= min(_SRI["per_script_without_sri_deduction"] * without_sri, _SRI["max_deduction"])
        issues.append(f"{without_sri} third-party scripts lack SRI (PCI 6.4.3 integrity violation risk)")

    return max(0, score), issues


# PCI 6.4.3 and 11.6.1 govern the pages that take payment, so grade those first
_PAYMENT_PATH_HINTS = ("checkout", "payment", "pay", "cart", "billing", "order")


def _headers_to_grade(crawl, site_url: str) -> tuple[str, dict[str, str]]:
    """Pick which page's headers represent the site.

    Prefers a checkout or payment page, then the homepage, and only then falls back to whatever
    was crawled first — the previous behaviour relied on dict insertion order, so a failed
    homepage fetch silently graded a random policy page instead.
    """
    headers = crawl.http_headers or {}
    if not headers:
        return "", {}

    for url, hdrs in headers.items():
        path = urlparse(url).path.lower()
        if any(hint in path for hint in _PAYMENT_PATH_HINTS):
            return url, hdrs

    for candidate in (site_url, site_url.rstrip("/"), site_url.rstrip("/") + "/"):
        if candidate in headers:
            return candidate, headers[candidate]

    url, hdrs = next(iter(headers.items()))
    return url, hdrs


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)

    try:
        crawl = state.crawl_result
        if crawl is None:
            raise ValueError("Crawl result not available — crawl must complete before PCI scan")

        scripts = crawl.scripts_found
        third_party = [s for s in scripts if not s.is_first_party and not s.is_inline]
        without_sri = [s for s in third_party if not s.has_sri]

        graded_url, graded_headers = _headers_to_grade(crawl, str(state.merchant_input.website_url))
        security_analysis = analyze_security_headers(graded_headers)

        header_score, header_issues = _score_headers(security_analysis)
        script_score, script_issues = _score_scripts(len(third_party), len(without_sri))
        total_score = min(100, header_score + script_score)

        pci_result = PCIResult(
            scripts_inventory=scripts,
            total_scripts=len(scripts),
            third_party_scripts=len(third_party),
            scripts_without_sri=len(without_sri),
            csp_header=security_analysis.get("csp", {}),
            hsts_header=security_analysis.get("hsts", {}),
            x_frame_options=security_analysis.get("x_frame_options", {}),
            x_content_type=security_analysis.get("x_content_type", {}),
            referrer_policy=security_analysis.get("referrer_policy", {}),
            security_score=total_score,
            critical_issues=header_issues + script_issues,
        )

        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="PCIScanner",
            action="PCI DSS v4.0.1 surface scan",
            result=f"Score {total_score}/100 — {len(pci_result.critical_issues)} issues found "
                   f"({len(third_party)} 3rd-party scripts, {len(without_sri)} without SRI; "
                   f"headers graded on {graded_url or 'no page'})",
            duration_ms=round(duration_ms, 1),
        )

        return {
            "pci_result": pci_result,
            "audit_log": [log],
        }

    except Exception as e:
        return failure(t0, "PCIScanner", "PCI DSS scan", e)
