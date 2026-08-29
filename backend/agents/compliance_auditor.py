from __future__ import annotations

import asyncio
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
# Exactly 10 subscriber digits, optional +91/0 trunk prefix, bounded by non-digits so the match
# cannot run on into an adjacent number (a house number, a PIN code, an id inside a script)
_PHONE_CANDIDATE = re.compile(r"(?<!\d)(?:(?:\+?91|0)[\s\-]?)?(?:\d[\s\-]?){9}\d(?!\d)")
# An Indian postal address carries a 6-digit PIN code; requiring one kills the "india appears in
# the footer" false positive that made has_address true for essentially every site
_PIN_CODE = re.compile(r"(?<!\d)[1-9]\d{5}(?!\d)")
_ADDRESS_KEYWORDS = (
    "address", "road", "street", "nagar", "colony", "sector", "lane", "marg", "plot",
    "floor", "building", "india",
)
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _load_rbi_db() -> dict:
    with _RBI_DB_PATH.open() as f:
        return json.load(f)


def _rbi_red_flag_gstins() -> set[str]:
    check = next((c for c in _load_rbi_db()["checks"] if c["id"] == "RBI-005"), {})
    return set(check.get("quality_criteria", {}).get("red_flags", []))


_RBI_RED_FLAG_GSTINS = _rbi_red_flag_gstins()


def _html_to_text(html: str) -> str:
    """Strip HTML tags and decode entities for plain-text keyword matching."""
    from bs4 import BeautifulSoup
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    # Normalize & so "Terms & Conditions" matches "terms and conditions"
    return re.sub(r"\s*&\s*", " and ", text)


def _policy_quality(html: str, check: dict) -> int:
    """Rule-based quality score 1-10 for a page already known to be the policy page."""
    text = _html_to_text(html)
    lowered = text.lower()
    body_keywords = check["search"].get("body_keywords", [])
    found_keywords = sum(1 for kw in body_keywords if kw.lower() in lowered)

    criteria = check.get("quality_criteria", {})
    if any(rf.lower() in lowered for rf in criteria.get("red_flags", [])):
        return 2  # present but placeholder/template

    coverage = (found_keywords / max(len(body_keywords), 1)) * 8
    depth = 2 if len(text.split()) > criteria.get("min_word_count", 100) else 0
    return min(10, max(1, int(coverage + depth)))


def _search_page_for_policy(html: str, check: dict) -> tuple[bool, int]:
    """Discovery heuristic: does this page look like the policy, and how good is it?"""
    text = _html_to_text(html).lower()
    body_keywords = check["search"].get("body_keywords", [])
    found_keywords = sum(1 for kw in body_keywords if kw.lower() in text)

    if found_keywords < 2:
        return False, 0
    return True, _policy_quality(html, check)


def _has_indian_phone(text: str) -> bool:
    """Accept both mobile and STD-code landline numbers.

    A mobile-only pattern rejected legitimate landlines such as +91-522-4001-234, which is a
    false 'no phone number' gap against a merchant that publishes one.
    """
    for match in _PHONE_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        # Indian subscriber numbers are 10 digits; mobiles start 6-9, landlines 2-8 by STD code
        if len(digits) == 10 and digits[0] in "23456789":
            return True
    return False


def _check_contact_page(html: str) -> tuple[bool, list[str]]:
    """Check visible contact details.

    Runs on extracted text, not raw HTML: script bodies, base64 blobs and query strings used to
    satisfy the phone regex, and 'road' matched inside 'broadcast', so almost every site passed.
    """
    issues: list[str] = []
    text = _html_to_text(html)
    lowered = text.lower()
    has_email = bool(_EMAIL_PATTERN.search(text))
    has_phone = _has_indian_phone(text)
    has_address = bool(_PIN_CODE.search(text)) and any(
        kw in lowered for kw in _ADDRESS_KEYWORDS
    )

    if not has_email:
        issues.append("No email address found on contact page")
    if not has_phone:
        issues.append("No Indian phone number found on contact page")
    if not has_address:
        issues.append("No physical address found — RBI requires a physical business address")

    found = has_email  # Minimum: email present
    return found, issues


_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _is_placeholder_gstin(gstin: str) -> bool:
    """Reject dummy GSTINs — the knowledge base red flags plus repeated-character fillers."""
    if gstin in _RBI_RED_FLAG_GSTINS:
        return True
    letters = gstin[2:7]
    return len(set(letters)) == 1


def _check_gst_display(all_html: str) -> tuple[bool, str | None]:
    """A GSTIN must be displayed to the customer, so commented-out markup does not count."""
    visible = _HTML_COMMENT.sub(" ", all_html)
    for match in _GST_PATTERN.finditer(visible):
        if not _is_placeholder_gstin(match.group(0)):
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

            # The crawler already matched this URL by path or link text, so the page exists —
            # only its quality is in question. A 40-word stub is "inadequate", not "missing".
            page_url = identified.get(policy_type.lower().replace(" ", "_"))
            page_html = pages.get(page_url, "") if page_url else ""
            found = bool(page_html)
            quality_score = _policy_quality(page_html, check_def) if found else 0

            # Otherwise look for the policy inline on some other page
            if not found:
                for url, html in pages.items():
                    matched, score = _search_page_for_policy(html, check_def)
                    if matched:
                        page_url, page_html, found, quality_score = url, html, True, score
                        break

            if not found:
                return ComplianceCheck(
                    name=check_def["name"],
                    check_id=check_id,
                    found=False,
                    severity=Severity(check_def["severity"]),
                    issues=[f"{check_def['name']} not found on the website"],
                )

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

        # Run policy checks concurrently — one failing check must not abort the others
        results = await asyncio.gather(
            _score_policy("RBI-001", "refund"),
            _score_policy("RBI-002", "privacy"),
            _score_policy("RBI-003", "terms"),
            return_exceptions=True,
        )
        refund_check, privacy_check, terms_check = [
            r if isinstance(r, ComplianceCheck) else ComplianceCheck(
                name=name, check_id=cid, issues=[f"Check failed: {r}"], severity=Severity.CRITICAL
            )
            for r, name, cid in zip(
                results,
                ("Refund Policy", "Privacy Policy", "Terms & Conditions"),
                ("RBI-001", "RBI-002", "RBI-003"),
            )
        ]

        business_category = _detect_business_category(all_html)

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
            "audit_log": [log],
        }
        # A silent LLM failure would otherwise pass every policy at the threshold score
        if any((c.details or "").startswith("LLM scoring unavailable") for c in (refund_check, privacy_check, terms_check)):
            update["errors"] = [
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
            "errors": [f"ComplianceAuditor failed: {e}"],
            "audit_log": [log],
        }


def _detect_business_category(html: str) -> str:
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
