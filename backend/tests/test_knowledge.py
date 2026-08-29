"""Every rule the knowledge base declares must be applied by code.

Half of each check used to be inert: `url_patterns`, `link_text_patterns`, `footer_patterns`,
`required_elements`, `gst_pattern`, `must_contain_topics` and `business_type_variations` were
declared and never read, while forked copies of the same lists lived in `crawler_tools.py` and
`pci_scanner.py` and had already drifted. These tests keep the files load bearing, which is also
what makes the public checks page honest.
"""
import json
from pathlib import Path

import pytest

from backend import knowledge as kb

_RBI = json.loads((Path("backend/knowledge/rbi_mdd_checklist.json")).read_text())
_PCI = json.loads((Path("backend/knowledge/pci_dss_surface_checks.json")).read_text())


def _rbi(check_id: str) -> dict:
    return next(c for c in _RBI["checks"] if c["id"] == check_id)


class TestLoaders:
    def test_rbi_checks_load(self):
        assert len(kb.rbi_checks()) == 6
        assert [c["id"] for c in kb.rbi_checks()] == [f"RBI-00{i}" for i in range(1, 7)]

    def test_pci_checks_load(self):
        assert len(kb.pci_checks()) == 5

    def test_lookup_by_id(self):
        assert kb.rbi_check("RBI-001")["name"].startswith("Refund")
        assert kb.pci_check("PCI-004")["requirement"] == "11.6.1"


class TestPolicyDiscoveryIsGrounded:
    """The crawler's URL and link-text maps must come from the checklist, not a private copy."""

    @pytest.mark.parametrize(
        "check_id,ptype",
        [("RBI-001", "refund"), ("RBI-002", "privacy"), ("RBI-003", "terms"), ("RBI-004", "contact")],
    )
    def test_url_patterns_match_the_checklist(self, check_id, ptype):
        declared = set(_rbi(check_id)["search"]["url_patterns"])
        assert declared == set(kb.policy_url_patterns()[ptype])

    @pytest.mark.parametrize(
        "check_id,ptype",
        [("RBI-001", "refund"), ("RBI-002", "privacy"), ("RBI-003", "terms"), ("RBI-004", "contact")],
    )
    def test_link_text_includes_footer_phrases(self, check_id, ptype):
        check = _rbi(check_id)["search"]
        declared = set(check["link_text_patterns"]) | set(check.get("footer_patterns", []))
        assert declared == set(kb.policy_link_text_patterns()[ptype])

    def test_money_back_pattern_is_applied(self):
        """The forked crawler copy was missing /money-back that the checklist declares."""
        assert "/money-back" in kb.policy_url_patterns()["refund"]


class TestPaymentPagePatterns:
    def test_payment_patterns_come_from_the_pci_file(self):
        assert set(kb.payment_page_patterns()) == set(_PCI["payment_page_patterns"])

    def test_checkout_is_recognised(self):
        assert "checkout" in kb.payment_page_patterns()


class TestNoInertRules:
    """A field declared in the knowledge base but read by nothing is a claim we do not honour."""

    LIVE_RBI_FIELDS = {
        "url_patterns", "link_text_patterns", "footer_patterns", "body_keywords",
        "min_word_count", "red_flags", "must_contain_topics", "required_elements",
        "gst_pattern", "normalization_rules", "known_mismatch_patterns",
        "min_similarity_threshold",
    }

    @staticmethod
    def _backend_source() -> str:
        """Every non-test backend source file, concatenated.

        Scanning the source is the check that matters. Asserting against a hand written mapping
        would only prove the mapping exists, which is how these fields stayed inert while a
        comment claimed the knowledge base was the single source of truth.
        """
        root = Path("backend")
        parts = []
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            parts.append(path.read_text(encoding="utf-8"))
        return "\n".join(parts)

    def test_every_declared_field_is_read_somewhere(self):
        source = self._backend_source()
        declared: set[str] = set()
        for check in _RBI["checks"]:
            declared |= set(check.get("search", {}))
            declared |= set(check.get("quality_criteria", {}))

        # Require a real dict access, not a mention. Listing a field as a key in FIELD_READERS
        # would otherwise satisfy a plain substring scan and the test would prove nothing.
        def is_read(field: str) -> bool:
            return any(
                token in source
                for token in (
                    f'get("{field}"', f"get('{field}'",
                    f'["{field}"]', f"['{field}']",
                )
            )

        unread = sorted(f for f in declared if not is_read(f))
        assert not unread, (
            f"declared in rbi_mdd_checklist.json but read by no backend code: {unread}. "
            "Either apply the rule or remove it; publishing a rule the engine ignores is a "
            "claim the artifact does not support."
        )
