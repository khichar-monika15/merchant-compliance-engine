"""Single reader for the compliance knowledge base.

Every rule the engine applies is declared in `backend/knowledge/*.json` and loaded here. Modules
used to keep private copies of the same lists, which drifted: the crawler's refund URL list had
lost `/money-back`, and the payment-page hints existed twice in slightly different forms.

`KNOWLEDGE_FIELDS` classifies every key in every knowledge file. `test_no_inert_declarations.py`
enforces it, so a key that is neither applied by a named module nor deliberately marked as display
metadata fails the build. Adding a rule therefore forces the author to say who honours it.

The predecessor of this mapping, `FIELD_READERS`, was itself read by nothing while its docstring
claimed a test enforced it. The registry below is imported by the test, which is the difference.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent / "knowledge"


def applied(module: str) -> tuple[str, str]:
    """A rule. `module` must contain a real dict access for this key.

    Named per module rather than "somewhere in the backend" because key names collide across
    files: `reason`, `category`, `headers` and `name` each appear in more than one, so a global
    scan marks a field read when a different file's identically named key is the one being read.
    """
    return ("applied", module)


def display() -> tuple[str, str]:
    """Metadata for the checks page. No engine code should read it, and it must reach the API."""
    return ("display", "")


def dynamic(parent: str) -> tuple[str, str]:
    """A data key rather than a rule name, reached by iterating `parent` (a stack name, a
    business type, a CSP band). Honoured when its parent block is."""
    return ("dynamic", parent)


# file -> declared key -> how it is honoured.
KNOWLEDGE_FIELDS: dict[str, dict[str, tuple[str, str]]] = {
    "rbi_mdd_checklist.json": {
        "version": applied("backend.api.routes"),
        "source": applied("backend.api.routes"),
        "checks": applied("backend.knowledge"),
        "id": applied("backend.knowledge"),
        "name": applied("backend.agents.compliance_auditor"),
        "category": display(),
        "description": display(),
        "severity": applied("backend.agents.compliance_auditor"),
        "detection_strategy": applied("backend.agents.compliance_auditor"),
        "search": applied("backend.agents.compliance_auditor"),
        "url_patterns": applied("backend.knowledge"),
        "link_text_patterns": applied("backend.knowledge"),
        "footer_patterns": applied("backend.knowledge"),
        "body_keywords": applied("backend.agents.compliance_auditor"),
        "quality_criteria": applied("backend.agents.compliance_auditor"),
        "min_word_count": applied("backend.agents.compliance_auditor"),
        "must_contain_topics": applied("backend.agents.compliance_auditor"),
        "red_flags": applied("backend.agents.compliance_auditor"),
        "gst_pattern": applied("backend.agents.compliance_auditor"),
        "allowed_leading_digits": applied("backend.agents.compliance_auditor"),
        "required_elements": applied("backend.agents.compliance_auditor"),
        "physical_address": applied("backend.agents.compliance_auditor"),
        "pin_code_pattern": applied("backend.agents.compliance_auditor"),
        "locality_keywords": applied("backend.agents.compliance_auditor"),
        "phone": applied("backend.agents.compliance_auditor"),
        "candidate_pattern": applied("backend.agents.compliance_auditor"),
        "subscriber_digits": applied("backend.agents.compliance_auditor"),
        "email": applied("backend.agents.compliance_auditor"),
        "note": display(),
        "business_type_variations": applied("backend.agents.compliance_auditor"),
        "ecommerce": dynamic("business_type_variations"),
        "saas": dynamic("business_type_variations"),
        "services": dynamic("business_type_variations"),
        "food_delivery": dynamic("business_type_variations"),
        "extra_topics": applied("backend.agents.compliance_auditor"),
        "normalization_rules": applied("backend.tools.name_matcher"),
        "pattern": applied("backend.tools.name_matcher"),
        "replacement": applied("backend.tools.name_matcher"),
        "ignore_case": applied("backend.tools.name_matcher"),
        "known_mismatch_patterns": applied("backend.tools.name_matcher"),
        "min_similarity_threshold": applied("backend.tools.name_matcher"),
    },
    "pci_dss_surface_checks.json": {
        "version": applied("backend.api.routes"),
        "source": applied("backend.api.routes"),
        "payment_page_patterns": applied("backend.knowledge"),
        "checks": applied("backend.knowledge"),
        "id": applied("backend.knowledge"),
        "name": applied("backend.agents.pci_scanner"),
        "requirement": applied("backend.agents.pci_scanner"),
        "description": display(),
        "severity": applied("backend.agents.pci_scanner"),
        "notes": display(),
        "scoring": applied("backend.agents.pci_scanner"),
        "max_points": applied("backend.agents.pci_scanner"),
        "deductions": applied("backend.agents.pci_scanner"),
        "condition": applied("backend.agents.pci_scanner"),
        "points": applied("backend.agents.pci_scanner"),
        "reason": applied("backend.agents.pci_scanner"),
        "per_script_without_sri_deduction": applied("backend.agents.pci_scanner"),
        "max_deduction": applied("backend.agents.pci_scanner"),
        "known_exemptions": applied("backend.agents.pci_scanner"),
        "no_csp_deduction": applied("backend.agents.pci_scanner"),
        "weak_csp_deduction": applied("backend.agents.pci_scanner"),
        "moderate_csp_deduction": applied("backend.agents.pci_scanner"),
        "strong_csp_deduction": applied("backend.agents.pci_scanner"),
        "grading": applied("backend.tools.csp_parser"),
        "strong": dynamic("grading"),
        "moderate": dynamic("grading"),
        "weak": dynamic("grading"),
        "none": dynamic("grading"),
        "score_min": applied("backend.tools.csp_parser"),
        "headers": applied("backend.agents.pci_scanner"),
    },
    "script_risk_database.json": {
        "version": applied("backend.api.routes"),
        "last_updated": display(),
        "notes": display(),
        "low_risk": applied("backend.tools.script_analyzer"),
        "medium_risk": applied("backend.tools.script_analyzer"),
        "high_risk_indicators": applied("backend.tools.script_analyzer"),
        "domains": applied("backend.tools.script_analyzer"),
        "category": applied("backend.tools.script_analyzer"),
    },
    "tech_stack_signatures.json": {
        "version": applied("backend.api.routes"),
        "stacks": applied("backend.agents.integration_advisor"),
        "shopify": dynamic("stacks"),
        "woocommerce": dynamic("stacks"),
        "wordpress": dynamic("stacks"),
        "nextjs": dynamic("stacks"),
        "react": dynamic("stacks"),
        "vue_nuxt": dynamic("stacks"),
        "django": dynamic("stacks"),
        "laravel": dynamic("stacks"),
        "static_html": dynamic("stacks"),
        "name": applied("backend.tools.crawler_tools"),
        "detection": applied("backend.tools.crawler_tools"),
        "html_contains": applied("backend.tools.crawler_tools"),
        "meta": applied("backend.tools.crawler_tools"),
        "content_prefix": applied("backend.tools.crawler_tools"),
        "headers": applied("backend.tools.crawler_tools"),
        "x-powered-by": dynamic("headers"),
        "x-frame-options": dynamic("headers"),
        "x-content-type-options": dynamic("headers"),
        "cookies": applied("backend.tools.crawler_tools"),
        "razorpay_recommendation": applied("backend.agents.integration_advisor"),
        "product": applied("backend.agents.integration_advisor"),
        "reason": applied("backend.agents.integration_advisor"),
        "integration_method": applied("backend.agents.integration_advisor"),
        "starter_template": applied("backend.agents.integration_advisor"),
        "docs_url": applied("backend.agents.integration_advisor"),
    },
}

# RBI check id -> the page type the crawler labels it with
_CHECK_TO_PAGE_TYPE = {
    "RBI-001": "refund",
    "RBI-002": "privacy",
    "RBI-003": "terms",
    "RBI-004": "contact",
}


@lru_cache(maxsize=None)
def _load(filename: str) -> dict:
    with (_DIR / filename).open() as f:
        return json.load(f)


def rbi_document() -> dict:
    return _load("rbi_mdd_checklist.json")


def pci_document() -> dict:
    return _load("pci_dss_surface_checks.json")


def script_risk_document() -> dict:
    """The third-party script risk taxonomy behind PCI-003.

    PCI-003 used to carry its own copy of this inside the checklist. The copy drifted, was read
    by nothing, and was still served to the checks page.
    """
    return _load("script_risk_database.json")


def tech_stack_document() -> dict:
    return _load("tech_stack_signatures.json")


def rbi_checks() -> list[dict]:
    return rbi_document()["checks"]


def pci_checks() -> list[dict]:
    return pci_document()["checks"]


def rbi_check(check_id: str) -> dict:
    return next(c for c in rbi_checks() if c["id"] == check_id)


def pci_check(check_id: str) -> dict:
    return next(c for c in pci_checks() if c["id"] == check_id)


@lru_cache(maxsize=1)
def policy_url_patterns() -> dict[str, list[str]]:
    """Page type -> URL fragments that identify it, straight from each check's `search` block."""
    return {
        page_type: list(rbi_check(check_id)["search"].get("url_patterns", []))
        for check_id, page_type in _CHECK_TO_PAGE_TYPE.items()
    }


@lru_cache(maxsize=1)
def policy_link_text_patterns() -> dict[str, list[str]]:
    """Page type -> link text that identifies it.

    Footer phrases are folded in here rather than given their own matcher: they are link text,
    just more specific ("refund policy" rather than "refund").
    """
    result: dict[str, list[str]] = {}
    for check_id, page_type in _CHECK_TO_PAGE_TYPE.items():
        search = rbi_check(check_id)["search"]
        merged = list(search.get("link_text_patterns", [])) + list(search.get("footer_patterns", []))
        # Preserve order, drop duplicates
        result[page_type] = list(dict.fromkeys(merged))
    return result


@lru_cache(maxsize=1)
def payment_page_patterns() -> list[str]:
    """Path fragments that mark a checkout or payment page.

    PCI DSS 6.4.3 and 11.6.1 are about payment pages specifically, so the list belongs with the
    PCI checks rather than duplicated in the crawler and the scanner.
    """
    return list(pci_document()["payment_page_patterns"])


def page_type(check_id: str) -> str:
    """The crawler's label for the page a check looks for."""
    return _CHECK_TO_PAGE_TYPE[check_id]


def quality_criteria(check_id: str) -> dict:
    return rbi_check(check_id).get("quality_criteria", {})
