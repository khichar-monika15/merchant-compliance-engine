"""Single reader for the compliance knowledge base.

Every rule the engine applies is declared in `backend/knowledge/*.json` and loaded here. Modules
used to keep private copies of the same lists, which drifted: the crawler's refund URL list had
lost `/money-back`, and the payment-page hints existed twice in slightly different forms.

`FIELD_READERS` records which module consumes each declared field. A field with no reader is a
rule we publish but do not honour, and `test_knowledge.py` fails on one.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent / "knowledge"

# Declared field -> the module that applies it. Kept here so the mapping is checkable.
FIELD_READERS: dict[str, str] = {
    "url_patterns": "tools.crawler_tools",
    "link_text_patterns": "tools.crawler_tools",
    "footer_patterns": "tools.crawler_tools",
    "body_keywords": "agents.compliance_auditor",
    "min_word_count": "agents.compliance_auditor",
    "red_flags": "agents.compliance_auditor",
    "must_contain_topics": "agents.compliance_auditor",
    "required_elements": "agents.compliance_auditor",
    "gst_pattern": "agents.compliance_auditor",
    "normalization_rules": "tools.name_matcher",
    "known_mismatch_patterns": "tools.name_matcher",
    "min_similarity_threshold": "tools.name_matcher",
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


def body_keywords(check_id: str) -> list[str]:
    return list(rbi_check(check_id)["search"].get("body_keywords", []))


def quality_criteria(check_id: str) -> dict:
    return rbi_check(check_id).get("quality_criteria", {})
