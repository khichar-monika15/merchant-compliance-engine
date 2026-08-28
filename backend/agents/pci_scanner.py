from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.models.schemas import AuditLogEntry, EngineState, PCIResult, ScriptInfo
from backend.tools.csp_parser import analyze_security_headers

_PCI_DB_PATH = Path(__file__).parent.parent / "knowledge" / "pci_dss_surface_checks.json"


def _load_pci_db() -> dict:
    with _PCI_DB_PATH.open() as f:
        return json.load(f)


def _score_headers(security_analysis: dict) -> tuple[int, list[str]]:
    """Score security headers out of 25, return (score, critical_issues)."""
    score = 25
    issues: list[str] = []

    csp = security_analysis.get("csp", {})
    if not csp.get("present"):
        score -= 20
        issues.append("CSP header missing (PCI 11.6.1)")
    elif csp.get("strength") == "weak":
        score -= 10
        issues.append("CSP is present but weak")
    elif csp.get("strength") == "moderate":
        score -= 5

    hsts = security_analysis.get("hsts", {})
    if not hsts.get("present"):
        score -= 7
        issues.append("HSTS missing — HTTPS not enforced")

    xfo = security_analysis.get("x_frame_options", {})
    if not xfo.get("present"):
        score -= 6
        issues.append("X-Frame-Options missing — clickjacking risk")

    xcto = security_analysis.get("x_content_type", {})
    if not xcto.get("present"):
        score -= 6
        issues.append("X-Content-Type-Options: nosniff missing")

    rp = security_analysis.get("referrer_policy", {})
    if not rp.get("present"):
        score -= 6
        issues.append("Referrer-Policy missing")

    return max(0, score), issues


def _score_scripts(third_party_count: int, without_sri: int) -> tuple[int, list[str]]:
    """Score script inventory out of 50, return (score, issues)."""
    score = 50
    issues: list[str] = []

    if third_party_count > 20:
        score -= 15
        issues.append(f"{third_party_count} third-party scripts loaded — very high risk surface area")
    elif third_party_count > 10:
        score -= 10
        issues.append(f"{third_party_count} third-party scripts loaded (PCI 6.4.3 requires justification for each)")

    per_script = min(3 * without_sri, 25)
    score -= per_script
    if without_sri > 0:
        issues.append(f"{without_sri} third-party scripts lack SRI (PCI 6.4.3 integrity violation risk)")

    return max(0, score), issues


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)

    try:
        crawl = state.crawl_result
        if crawl is None:
            raise ValueError("Crawl result not available — crawl must complete before PCI scan")

        scripts = crawl.scripts_found
        third_party = [s for s in scripts if not s.is_first_party and not s.is_inline]
        without_sri = [s for s in third_party if not s.has_sri]

        # Analyse security headers from homepage (first URL in http_headers)
        all_headers = crawl.http_headers
        homepage_headers: dict[str, str] = {}
        if all_headers:
            homepage_headers = next(iter(all_headers.values()), {})

        security_analysis = analyze_security_headers(homepage_headers)

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
                   f"({len(third_party)} 3rd-party scripts, {len(without_sri)} without SRI)",
            duration_ms=round(duration_ms, 1),
        )

        return {
            "pci_result": pci_result,
            "audit_log": state.audit_log + [log],
        }

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="PCIScanner",
            action="PCI DSS scan",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "errors": state.errors + [f"PCIScanner failed: {e}"],
            "audit_log": state.audit_log + [log],
        }
