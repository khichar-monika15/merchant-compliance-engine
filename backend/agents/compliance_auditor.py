from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.tools.llm_client import llm_complete
from backend.models.schemas import (
    AuditLogEntry,
    ComplianceCheck,
    ComplianceResult,
    EngineState,
    Severity,
)

_RBI_DB_PATH = Path(__file__).parent.parent / "knowledge" / "rbi_mdd_checklist.json"
_GST_PATTERN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}")
_PHONE_IN = re.compile(r"(\+91|0)?[\s\-]?[6-9]\d{9}")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _load_rbi_db() -> dict:
    with _RBI_DB_PATH.open() as f:
        return json.load(f)


def _html_to_text(html: str) -> str:
    """Strip HTML tags and decode entities for plain-text keyword matching."""
    from bs4 import BeautifulSoup
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    # Normalize & so "Terms & Conditions" matches "terms and conditions"
    return re.sub(r"\s*&\s*", " and ", text)


def _search_page_for_policy(html: str, check: dict) -> tuple[bool, int]:
    """Rule-based: search for policy presence and estimate quality score."""
    text = _html_to_text(html)
    body_keywords = check["search"].get("body_keywords", [])
    found_keywords = sum(1 for kw in body_keywords if kw.lower() in text.lower())
    found = found_keywords >= 2

    if not found:
        return False, 0

    word_count = len(text.split())
    min_words = check.get("quality_criteria", {}).get("min_word_count", 100)
    red_flags = check.get("quality_criteria", {}).get("red_flags", [])

    if any(rf.lower() in text.lower() for rf in red_flags):
        return True, 2  # Present but placeholder/template

    quality = min(10, max(2, int((found_keywords / max(len(body_keywords), 1)) * 8 + (2 if word_count > min_words else 0))))
    return True, quality


def _check_contact_page(html: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    has_email = bool(_EMAIL_PATTERN.search(html))
    has_phone = bool(_PHONE_IN.search(html))
    has_address = len(html) > 100 and any(
        kw in html.lower() for kw in ["address", "road", "street", "nagar", "colony", "india", "bangalore", "mumbai", "delhi", "chennai", "hyderabad", "pune"]
    )

    if not has_email:
        issues.append("No email address found on contact page")
    if not has_phone:
        issues.append("No Indian phone number found on contact page")
    if not has_address:
        issues.append("No physical address found — RBI requires a physical business address")

    found = has_email  # Minimum: email present
    return found, issues


def _check_gst_display(all_html: str) -> tuple[bool, str | None]:
    match = _GST_PATTERN.search(all_html)
    if match:
        return True, match.group(0)
    return False, None


async def _llm_quality_score(
    policy_text: str, policy_type: str, business_type: str, fallback: int
) -> tuple[int, str]:
    """Score policy quality 0-10 with the LLM, falling back to the rule-based score."""
    prompt = f"""You are a compliance analyst evaluating merchant policies for RBI Payment Aggregator guidelines.

Policy type: {policy_type}
Merchant business type: {business_type or 'unknown'}

Policy content (first 2000 chars):
{policy_text[:2000]}

Rate this policy quality on a scale of 0-10 where:
0-2: Missing or placeholder/template
3-4: Present but extremely thin (under 100 words, no specifics)
5-6: Present but incomplete (missing key topics like timeline/contact/eligibility)
7-8: Adequate (covers main topics, has specifics)
9-10: Comprehensive (all topics, business-specific, legally sound)

Respond in JSON only:
{{"score": <0-10>, "issues": ["issue1", "issue2"], "details": "brief assessment"}}"""

    try:
        text = await llm_complete(prompt, max_tokens=256)
        if not text:
            return fallback, "LLM scoring unavailable — rule-based score used"
        text = _strip_code_fence(text)
        data = json.loads(text)
        return int(data.get("score", fallback)), data.get("details", "")
    except Exception as e:
        return fallback, f"LLM scoring unavailable ({type(e).__name__}) — rule-based score used"


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, with or without a language tag."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    return re.sub(r"\s*```$", "", text).strip()


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)

    try:
        rbi_db = _load_rbi_db()
        crawl = state.crawl_result
        pages = crawl.pages_found if crawl else {}
        identified = crawl.identified_pages if crawl else {}
        all_html = " ".join(pages.values())

        async def _score_policy(check_id: str, policy_type: str) -> ComplianceCheck:
            check_def = next((c for c in rbi_db["checks"] if c["id"] == check_id), None)
            if not check_def:
                return ComplianceCheck(name=policy_type, check_id=check_id)

            page_url = identified.get(policy_type.lower().replace(" ", "_"))
            page_html = pages.get(page_url, "") if page_url else ""

            # Fall back to searching all pages if not identified
            if not page_html:
                for url, html in pages.items():
                    found, _ = _search_page_for_policy(html, check_def)
                    if found:
                        page_url = url
                        page_html = html
                        break

            if not page_html:
                return ComplianceCheck(
                    name=check_def["name"],
                    check_id=check_id,
                    found=False,
                    severity=Severity(check_def["severity"]),
                    issues=[f"{check_def['name']} not found on the website"],
                )

            # Rule-based presence detection
            found, quality_score = _search_page_for_policy(page_html, check_def)

            # LLM semantic quality scoring, falling back to the rule-based score above
            details = ""
            llm_issues: list[str] = []
            if found:
                business_type = state.merchant_input.business_type or "unknown"
                quality_score, details = await _llm_quality_score(
                    _html_to_text(page_html), check_def["name"], business_type, fallback=quality_score
                )
                if quality_score < 5:
                    llm_issues.append(f"Policy content appears inadequate: {details}")

            return ComplianceCheck(
                name=check_def["name"],
                check_id=check_id,
                found=found,
                url=page_url,
                quality_score=quality_score,
                severity=Severity(check_def["severity"]),
                issues=llm_issues,
                details=details or None,
            )

        # Check RBI-004 contact info
        contact_url = identified.get("contact")
        contact_html = pages.get(contact_url, "") if contact_url else ""
        if not contact_html:
            for url, html in pages.items():
                if "contact" in url.lower():
                    contact_html = html
                    contact_url = url
                    break

        contact_found, contact_issues = _check_contact_page(contact_html or all_html)
        contact_check = ComplianceCheck(
            name="Contact Information",
            check_id="RBI-004",
            found=contact_found,
            url=contact_url,
            quality_score=max(0, 10 - len(contact_issues) * 3),
            severity=Severity.CRITICAL,
            issues=contact_issues,
        )

        # GST display check
        gst_found, gst_number = _check_gst_display(all_html)
        gst_check = ComplianceCheck(
            name="GST Display",
            check_id="RBI-005",
            found=gst_found,
            quality_score=10 if gst_found else 0,
            severity=Severity.WARNING,
            issues=[] if gst_found else ["GST registration number not displayed on website"],
            details=gst_number,
        )

        # Run policy checks concurrently
        refund_check, privacy_check, terms_check = await _concurrent_checks(
            _score_policy("RBI-001", "refund"),
            _score_policy("RBI-002", "privacy"),
            _score_policy("RBI-003", "terms"),
        )

        # Detect business category
        business_category = _detect_business_category(all_html, crawl.tech_stack_signals if crawl else {})

        # Compute overall score
        checks = [refund_check, privacy_check, terms_check, contact_check]
        critical_passed = sum(1 for c in checks if c.found and c.quality_score >= 5)
        overall = int((critical_passed / len(checks)) * 80) + (20 if gst_found else 0)

        result = ComplianceResult(
            refund_policy=refund_check,
            privacy_policy=privacy_check,
            terms_conditions=terms_check,
            contact_info=contact_check,
            gst_display=gst_check,
            business_category=business_category,
            overall_score=overall,
        )

        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        passed = sum(1 for c in [refund_check, privacy_check, terms_check, contact_check, gst_check] if c.found)
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="ComplianceAuditor",
            action="RBI MDD compliance audit",
            result=f"Score {overall}/100 — {passed}/5 checks passed",
            duration_ms=round(duration_ms, 1),
        )

        update: dict = {
            "compliance_result": result,
            "audit_log": state.audit_log + [log],
        }
        # A silent LLM failure would otherwise pass every policy at the threshold score
        if any((c.details or "").startswith("LLM scoring unavailable") for c in (refund_check, privacy_check, terms_check)):
            update["errors"] = state.errors + [
                "ComplianceAuditor: LLM unavailable — policy quality scored by rules only"
            ]
        return update

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="ComplianceAuditor",
            action="RBI compliance audit",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "errors": state.errors + [f"ComplianceAuditor failed: {e}"],
            "audit_log": state.audit_log + [log],
        }


async def _concurrent_checks(*coros):
    import asyncio
    return await asyncio.gather(*coros)


def _detect_business_category(html: str, tech_signals: dict) -> str:
    html_lower = html.lower()
    if any(kw in html_lower for kw in ["add to cart", "buy now", "checkout", "product", "shop now", "order online"]):
        return "ecommerce"
    if any(kw in html_lower for kw in ["subscription", "per month", "pricing plan", "free trial", "saas", "software", "dashboard"]):
        return "saas"
    if any(kw in html_lower for kw in ["our services", "book appointment", "consultation", "hourly rate", "quote"]):
        return "services"
    if any(kw in html_lower for kw in ["delivery", "food", "restaurant", "order food", "menu"]):
        return "food_delivery"
    return "ecommerce"  # default
