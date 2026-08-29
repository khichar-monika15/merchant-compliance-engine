"""Graph wiring and state-channel semantics.

The pipeline previously ran on `StateGraph(dict)`, which compiles to a single `__root__`
channel: any node returning a partial dict silently replaced the entire state. It only worked
because every node happened to return the whole state. These tests pin the contract so a future
agent returning just its own key cannot wipe the report.
"""
import pytest
from langgraph.graph import END, StateGraph

from backend.agents.orchestrator import (
    GraphState,
    _route_after_crawl,
    _route_after_parallel,
    build_workflow,
)


def _run(nodes: list, seed: dict) -> dict:
    g = StateGraph(GraphState)
    previous = None
    for name, fn in nodes:
        g.add_node(name, fn)
        if previous is None:
            g.set_entry_point(name)
        else:
            g.add_edge(previous, name)
        previous = name
    g.add_edge(previous, END)
    return g.compile().invoke(seed)


class TestStateChannels:
    def test_partial_update_does_not_wipe_other_keys(self):
        final = _run(
            [
                ("a", lambda s: {"current_phase": "crawled"}),
                ("b", lambda s: {"compliance_result": {"overall_score": 42}}),
            ],
            {"merchant_input": {"pan_name": "Acme"}},
        )
        assert final["merchant_input"] == {"pan_name": "Acme"}, "seed state was wiped"
        assert final["current_phase"] == "crawled", "earlier node's write was wiped"
        assert final["compliance_result"] == {"overall_score": 42}

    def test_audit_log_accumulates_across_nodes(self):
        final = _run(
            [
                ("a", lambda s: {"audit_log": [{"agent": "WebCrawler"}]}),
                ("b", lambda s: {"audit_log": [{"agent": "PCIScanner"}]}),
            ],
            {"audit_log": []},
        )
        assert [e["agent"] for e in final["audit_log"]] == ["WebCrawler", "PCIScanner"]

    def test_errors_accumulate_across_nodes(self):
        final = _run(
            [
                ("a", lambda s: {"errors": ["first"]}),
                ("b", lambda s: {"errors": ["second"]}),
            ],
            {"errors": []},
        )
        assert final["errors"] == ["first", "second"]

    def test_scalar_channels_overwrite_rather_than_append(self):
        final = _run(
            [
                ("a", lambda s: {"current_phase": "crawled"}),
                ("b", lambda s: {"current_phase": "complete"}),
            ],
            {"current_phase": "queued"},
        )
        assert final["current_phase"] == "complete"


class TestRouting:
    def test_unreachable_site_produces_no_report(self):
        """A site we never reached must fail the scan, not get graded.

        The crawler swallows ERR_CONNECTION_REFUSED and returns an empty-but-successful result,
        so a typo'd URL used to score a confident Grade D — including PCI points for headers
        that were never fetched.
        """
        assert _route_after_crawl({"current_phase": "crawl_failed", "crawl_result": None}) == "abort"
        assert _route_after_crawl({"current_phase": "error", "crawl_result": {"pages_found": {}}}) == "abort"

    def test_crawl_that_retrieved_nothing_is_a_failure(self):
        """Zero pages retrieved is a failed crawl even when no exception was raised."""
        state = {"current_phase": "crawled", "crawl_result": {"pages_found": {}, "pages_crawled": 0}}
        assert _route_after_crawl(state) == "abort"

    def test_partial_crawl_still_analysed(self):
        state = {"current_phase": "crawl_failed", "crawl_result": {"pages_found": {"u": "<html>"}}}
        assert _route_after_crawl(state) == "parallel_analysis"

    def test_healthy_crawl_analysed(self):
        state = {"current_phase": "crawled", "crawl_result": {"pages_found": {"u": "<html>"}}}
        assert _route_after_crawl(state) == "parallel_analysis"

    def test_policy_generation_when_a_policy_is_thin(self):
        compliance = {
            "refund_policy": {"found": True, "quality_score": 3},
            "privacy_policy": {"found": True, "quality_score": 8},
            "terms_conditions": {"found": True, "quality_score": 8},
        }
        assert _route_after_parallel({"compliance_result": compliance}) == "generate_policies"

    def test_no_policy_generation_when_all_adequate(self):
        compliance = {
            "refund_policy": {"found": True, "quality_score": 8},
            "privacy_policy": {"found": True, "quality_score": 8},
            "terms_conditions": {"found": True, "quality_score": 7},
        }
        assert _route_after_parallel({"compliance_result": compliance}) == "generate_report"

    def test_missing_compliance_result_goes_straight_to_report(self):
        assert _route_after_parallel({"compliance_result": None}) == "generate_report"


class TestAgentConventions:
    """Project conventions that were documented but unenforced."""

    AGENTS = [
        "webcrawler", "compliance_auditor", "pci_scanner", "kyc_validator",
        "policy_generator", "integration_advisor", "report_generator",
    ]

    @staticmethod
    def _broken_state():
        """An EngineState that makes every agent fail, to exercise the error path."""
        from backend.models.schemas import EngineState, MerchantInput

        state = EngineState(merchant_input=MerchantInput(
            website_url="https://example.invalid",
            pan_name="X", gst_legal_name="X", bank_account_name="X",
        ))
        state.crawl_result = "not-a-crawl-result"  # type: ignore[assignment]
        return state

    @pytest.mark.parametrize("module_name", AGENTS)
    async def test_agent_never_raises_and_always_logs(self, module_name):
        import importlib

        agent = importlib.import_module(f"backend.agents.{module_name}")
        update = await agent.run(self._broken_state())

        assert isinstance(update, dict)
        assert update.get("audit_log"), f"{module_name} returned no audit entry"
        assert len(update["audit_log"]) == 1, "an agent contributes exactly one entry per run"

    @pytest.mark.parametrize("module_name", AGENTS)
    async def test_agent_returns_only_declared_state_keys(self, module_name):
        import importlib

        agent = importlib.import_module(f"backend.agents.{module_name}")
        update = await agent.run(self._broken_state())
        assert set(update) <= set(GraphState.__annotations__), (
            f"{module_name} writes keys the graph has no channel for: "
            f"{set(update) - set(GraphState.__annotations__)}"
        )


class TestProgressEvents:
    async def test_unreachable_site_does_not_report_a_completed_crawl(self):
        """The crawler must not emit 'crawl complete' for a site it never reached.

        Port 4999 is closed but ordinary. Port 1 is on Chromium's own blocked-port list, so
        navigating to it returns ERR_UNSAFE_PORT without ever attempting a connection, and the
        test passed without exercising the refusal path it names. Asserting on
        ERR_CONNECTION_REFUSED pins the real path: a missing browser or a blocked port produces a
        different message and fails here rather than passing for the wrong reason.
        """
        from backend.agents import orchestrator
        from backend.models.schemas import MerchantInput

        events: list[dict] = []

        async def capture(agent, message, pct, event_type="progress", done=False):
            events.append({"agent": agent, "message": message, "type": event_type, "done": done})

        await orchestrator.run_pipeline(
            MerchantInput(
                website_url="http://127.0.0.1:4999",
                pan_name="X", gst_legal_name="X", bank_account_name="X",
            ),
            progress_fn=capture,
        )

        crawler = [e for e in events if e["agent"] == "WebCrawler"]
        assert crawler, "the crawler emitted nothing"
        assert not any("complete" in e["message"].lower() for e in crawler), crawler
        assert any(e["type"] == "error" for e in crawler), crawler
        assert any("ERR_CONNECTION_REFUSED" in e["message"] for e in crawler), (
            "the crawl did not actually reach the network. A browser that never launched fails "
            f"here instead of passing as an unreachable site: {crawler}"
        )


class TestPipelineTimeout:
    async def test_timeout_returns_state_with_error_not_exception(self, monkeypatch):
        """A stalled scan must fail the job with a reason, not hang or raise."""
        import asyncio

        from backend.agents import orchestrator
        from backend.models.schemas import MerchantInput

        class _Stalled:
            async def ainvoke(self, _state):
                await asyncio.sleep(60)

        monkeypatch.setattr(orchestrator, "build_workflow", lambda progress_fn=None: _Stalled())

        merchant = MerchantInput(
            website_url="https://example.com",
            pan_name="Acme", gst_legal_name="Acme", bank_account_name="Acme",
        )
        state = await orchestrator.run_pipeline(merchant, timeout=0.05)

        assert state.readiness_report is None
        assert state.current_phase == "error"
        assert any("time limit" in e for e in state.errors)


class TestGraphShape:
    def test_workflow_compiles(self):
        assert build_workflow() is not None

    def test_declared_channels_are_per_key(self):
        """A regression guard: a single __root__ channel means partial updates wipe state."""
        channels = set(build_workflow().channels)
        assert "__root__" not in channels
        for key in ("audit_log", "errors", "crawl_result", "readiness_report"):
            assert key in channels, f"{key} has no dedicated channel"
