import pytest

from backend.agents.integration_advisor import _pick_primary_stack
from backend.agents.report_generator import _estimate_fix_time, _score_to_grade


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
