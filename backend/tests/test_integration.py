import pytest

from backend.agents.integration_advisor import _pick_primary_stack
from backend.agents.report_generator import _estimate_fix_time, _integration_score, _score_to_grade
from backend.models.schemas import IntegrationResult


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
        """RBI 100, KYC 100, PCI 100, integration 70 must still reach grade A."""
        overall = int(100 * 0.40 + 100 * 0.25 + 100 * 0.20 + 70 * 0.15)
        assert _score_to_grade(overall) == "A"
