import pytest

from backend.agents.integration_advisor import _pick_primary_stack
from backend.agents.report_generator import (
    _estimate_fix_time,
    _integration_score,
    _kyc_score,
    _score_to_grade,
)
from backend.models.schemas import IntegrationResult, KYCMatch, KYCResult


class TestPrimaryStackSelection:
    def test_shopify_wins_over_react(self):
        signals = {"shopify": ["cdn.shopify.com"], "react": ["ReactDOM"]}
        assert _pick_primary_stack(signals) == "shopify"

    def test_nextjs_over_react(self):
        signals = {"nextjs": ["__NEXT_DATA__"], "react": ["ReactDOM"]}
        assert _pick_primary_stack(signals) == "nextjs"

    def test_static_html_fallback(self):
        assert _pick_primary_stack({}) == "static_html"


class TestScoring:
    @pytest.mark.parametrize("score,grade", [
        (95, "A"), (90, "A"),
        (85, "B"), (75, "B"),
        (70, "C"), (50, "C"),
        (40, "D"), (25, "D"),
        (24, "F"), (0, "F"),
    ])
    def test_grade_mapping(self, score, grade):
        assert _score_to_grade(score) == grade

    def test_fix_time_no_gaps(self):
        result = _estimate_fix_time(0, 0)
        assert "ready" in result.lower()

    def test_fix_time_many_critical(self):
        result = _estimate_fix_time(5, 2)
        assert "week" in result.lower()

    def test_fix_time_warnings_only(self):
        result = _estimate_fix_time(0, 3)
        assert "hour" in result.lower()


class TestIntegrationScore:
    def test_no_integration_result(self):
        assert _integration_score(None) == 0

    def test_stack_detected_without_test_payment(self):
        """No Razorpay keys must not cost the merchant its grade."""
        result = IntegrationResult(
            detected_stack={"shopify": ["cdn.shopify.com"]},
            starter_code="<script>...</script>",
            test_payment_result={"success": False, "error": "no keys"},
        )
        assert _integration_score(result) == 70

    def test_test_payment_is_a_bonus(self):
        result = IntegrationResult(
            detected_stack={"shopify": ["cdn.shopify.com"]},
            starter_code="<script>...</script>",
            test_payment_result={"success": True, "order_id": "order_test"},
        )
        assert _integration_score(result) == 100

    def test_no_stack_detected(self):
        result = IntegrationResult(test_payment_result={"success": False})
        assert _integration_score(result) == 40

    def test_grade_a_reachable_without_razorpay_keys(self):
        """RBI 100, KYC 100, PCI 100, integration 70 must still reach grade A.

        The weights come from the scorer. Re-typing them here meant the test kept passing while
        the claim it makes went false, which is the failure this whole pass is about.
        """
        from backend.agents.report_generator import _WEIGHTS

        scores = {"rbi_compliance": 100, "kyc": 100, "pci": 100, "integration": 70}
        overall = int(sum(scores[key] * weight for key, weight in _WEIGHTS.items()))
        assert _score_to_grade(overall) == "A"


class TestKnowledgeBaseIntegrity:
    """Detection rules and Razorpay recommendations must stay in one place and stay complete."""

    def test_every_stack_has_a_recommendation_and_an_existing_template(self):
        from pathlib import Path

        from backend.agents.integration_advisor import _STARTER_DIR, _load_stacks_db

        for name, cfg in _load_stacks_db()["stacks"].items():
            rec = cfg.get("razorpay_recommendation")
            assert rec, f"{name} has no razorpay_recommendation"
            assert rec.get("product"), f"{name} has no product"
            template = rec.get("starter_template")
            assert template, f"{name} has no starter_template"
            assert Path(_STARTER_DIR / template).exists(), f"{name} points at missing {template}"

    def test_every_stack_the_code_can_pick_exists_in_the_knowledge_base(self):
        from backend.agents.integration_advisor import _load_stacks_db, _pick_primary_stack

        stacks = _load_stacks_db()["stacks"]
        for name in stacks:
            assert _pick_primary_stack({name: ["evidence"]}) in stacks

    def test_detection_rules_use_only_supported_keys(self):
        """A key the detector does not read is an inert rule — meta_name was one for months."""
        from backend.tools.crawler_tools import TECH_STACK_SIGNALS

        supported = {"html_contains", "meta", "headers", "cookies"}
        for name, cfg in TECH_STACK_SIGNALS.items():
            unknown = set(cfg.get("detection", {})) - supported
            assert not unknown, f"{name} declares unread detection keys: {unknown}"


class TestScoreBreakdown:
    """The breakdown the UI renders must reconcile with the headline score."""

    async def test_breakdown_sums_to_overall_score(self, basic_engine_state, crawl_result_no_policies):
        from backend.agents import kyc_validator, pci_scanner, report_generator

        basic_engine_state.crawl_result = crawl_result_no_policies
        for agent in (pci_scanner, kyc_validator):
            for key, value in (await agent.run(basic_engine_state)).items():
                setattr(basic_engine_state, key, value)

        update = await report_generator.run(basic_engine_state)
        report = update["readiness_report"]

        assert len(report.score_breakdown) == 4
        assert report.overall_score == int(sum(c.score * c.weight for c in report.score_breakdown))
        assert sum(c.weight for c in report.score_breakdown) == pytest.approx(1.0)
        for c in report.score_breakdown:
            assert 0 <= c.score <= 100


class TestKYCScore:
    @staticmethod
    def _result(matches: list[bool], similarity: float = 0.98) -> KYCResult:
        pairs = [KYCMatch(match=m, similarity=1.0 if m else similarity) for m in matches]
        return KYCResult(
            pan_gst_match=pairs[0], gst_bank_match=pairs[1], pan_bank_match=pairs[2],
            overall_consistent=all(matches), confidence=min(p.similarity for p in pairs),
        )

    def test_none(self):
        assert _kyc_score(None) == 0

    def test_all_pairs_match(self):
        assert _kyc_score(self._result([True, True, True])) == 100

    def test_high_similarity_mismatch_is_still_penalised(self):
        """0.98-similar names are a real onboarding blocker, not a 2-point deduction."""
        assert _kyc_score(self._result([False, False, False])) < 20

    def test_partial_match_scores_between(self):
        score = _kyc_score(self._result([True, True, False]))
        assert 60 < score < 90

    def test_never_reaches_a_clean_pass(self):
        assert _kyc_score(self._result([True, True, False], similarity=1.0)) <= 90
