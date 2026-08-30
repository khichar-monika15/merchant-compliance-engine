"""Graph wiring and state-channel semantics.

The pipeline previously ran on `StateGraph(dict)`, which compiles to a single `__root__`
channel: any node returning a partial dict silently replaced the entire state. It only worked
because every node happened to return the whole state. These tests pin the contract so a future
agent returning just its own key cannot wipe the report.
"""
from pathlib import Path

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
        """A crawl that got some pages is analysed. The route fans out to every analyser.

        Asserted against ANALYSERS rather than a written out list so the guard cannot drift from
        the graph if an analyser is ever added or renamed.
        """
        from backend.agents.orchestrator import ANALYSERS

        state = {"current_phase": "crawl_failed", "crawl_result": {"pages_found": {"u": "<html>"}}}
        assert _route_after_crawl(state) == [name for name, _ in ANALYSERS]

    def test_healthy_crawl_analysed(self):
        from backend.agents.orchestrator import ANALYSERS

        state = {"current_phase": "crawled", "crawl_result": {"pages_found": {"u": "<html>"}}}
        assert _route_after_crawl(state) == [name for name, _ in ANALYSERS]

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

    def test_a_thin_shipping_policy_still_routes_to_drafting(self):
        """RBI-007 is scored and gapped, so it has to be draftable too.

        The router inspected refund, privacy and terms only, so an ecommerce merchant whose sole
        gap was shipping paid the penalty while `shipping_ecommerce.md` sat unreachable.
        """
        compliance = {
            "refund_policy": {"found": True, "quality_score": 8},
            "privacy_policy": {"found": True, "quality_score": 8},
            "terms_conditions": {"found": True, "quality_score": 8},
            "shipping_policy": {"found": False, "quality_score": 0},
        }
        assert _route_after_parallel({"compliance_result": compliance}) == "generate_policies"

    def test_absent_shipping_check_is_not_treated_as_a_gap(self):
        """A SaaS merchant has no shipping key at all, and must not be sent to drafting for it."""
        compliance = {
            "refund_policy": {"found": True, "quality_score": 8},
            "privacy_policy": {"found": True, "quality_score": 8},
            "terms_conditions": {"found": True, "quality_score": 8},
            "shipping_policy": None,
        }
        assert _route_after_parallel({"compliance_result": compliance}) == "generate_report"


class TestEveryGapCarriesItsSource:
    """The landing page promises every gap has a source URL. Only compliance gaps had one.

    PCI gaps come from a page the scanner already identified, and KYC gaps come from the merchant's
    own submission rather than from the site, so each needs its own answer rather than a blank.
    """

    @staticmethod
    def _state_with_pci_and_kyc_gaps():
        from backend.models.schemas import (
            EngineState, KYCMatch, KYCResult, MerchantInput, PCIIssue, PCIResult, Severity,
        )

        state = EngineState(merchant_input=MerchantInput(
            website_url="https://shop.example.com",
            pan_name="Acme Pvt. Ltd.", gst_legal_name="ACME PRIVATE LIMITED",
            bank_account_name="Different Name Entirely",
        ))
        state.pci_result = PCIResult(
            security_score=40,
            graded_url="https://shop.example.com/checkout",
            issues=[PCIIssue(
                check_id="PCI-004",
                message="CSP header missing (PCI 11.6.1)",
                severity=Severity.CRITICAL,
            )],
        )
        mismatch = KYCMatch(match=False, similarity=0.2)
        state.kyc_result = KYCResult(
            pan_gst_match=mismatch, gst_bank_match=mismatch, pan_bank_match=mismatch,
            overall_consistent=False,
            common_mismatches=["PAN name and bank account name differ"],
        )
        return state

    async def test_pci_gaps_point_at_the_page_that_was_graded(self):
        from backend.agents import report_generator

        update = await report_generator.run(self._state_with_pci_and_kyc_gaps())
        report = update["readiness_report"]
        pci_gaps = [g for g in report.critical_gaps + report.warnings if g.category == "pci"]

        assert pci_gaps, "no PCI gap was produced"
        for gap in pci_gaps:
            assert gap.source_url == "https://shop.example.com/checkout", (
                f"PCI gap carries {gap.source_url!r} while the scanner knew the graded page"
            )

    async def test_every_gap_from_a_page_carries_that_page(self):
        """Compliance and PCI gaps come from pages, so both must name one.

        KYC gaps are excluded deliberately: they come from the three names the merchant typed in,
        not from the website, so there is no page to link. The landing page says so rather than
        promising a URL that could only ever be invented.
        """
        from backend.agents import report_generator

        update = await report_generator.run(self._state_with_pci_and_kyc_gaps())
        report = update["readiness_report"]

        blank = [
            (g.category, g.title) for g in report.critical_gaps + report.warnings
            if g.category != "kyc" and not g.source_url
        ]
        assert not blank, f"page-derived gaps with no source URL: {blank}"


class TestValidationAborts:
    """`_validate_input` computed errors that nothing acted on.

    The edge to the crawler was unconditional, so a merchant submitting three blank names got a
    fully graded report whose KYC axis compared blank to blank and called it a clean match.
    """

    @staticmethod
    def _blank_input():
        from backend.models.schemas import MerchantInput

        return MerchantInput(
            website_url="https://example.com",
            pan_name="   ", gst_legal_name="   ", bank_account_name="   ",
        )

    async def test_blank_names_are_rejected_before_crawling(self):
        from backend.agents import orchestrator

        state = await orchestrator.run_pipeline(self._blank_input())

        assert state.readiness_report is None, "a merchant with no names was graded"
        assert state.current_phase == "error"
        assert len(state.errors) == 3, state.errors

    def test_router_sends_a_failed_validation_to_the_end(self):
        from backend.agents.orchestrator import _route_after_validate

        assert _route_after_validate({"current_phase": "error"}) == "abort"
        assert _route_after_validate({"current_phase": "validated"}) == "crawl_website"

    async def test_a_metadata_endpoint_is_refused_without_launching_a_browser(self, monkeypatch):
        """The refusal has to happen in validation, before anything is fetched."""
        from backend.agents import orchestrator
        from backend.models.schemas import MerchantInput

        launched = False

        async def _should_not_run(state):
            nonlocal launched
            launched = True
            return {}

        monkeypatch.setattr(orchestrator.webcrawler, "run", _should_not_run)

        state = await orchestrator.run_pipeline(MerchantInput(
            website_url="http://169.254.169.254/latest/meta-data/",
            pan_name="Acme", gst_legal_name="Acme", bank_account_name="Acme",
        ))

        assert not launched, "the crawler was started for a link-local address"
        assert state.readiness_report is None
        assert any("Will not scan" in e for e in state.errors), state.errors


class TestAgentConventions:
    """Project conventions that were documented but unenforced."""

    AGENTS = [
        "webcrawler", "compliance_auditor", "pci_scanner", "kyc_validator",
        "policy_generator", "integration_advisor", "report_generator",
    ]

    # A corrupt crawl_result breaks exactly the agents that read it. The other three take their
    # input from elsewhere and complete normally, so a docstring claiming this state makes every
    # agent fail was wrong, and the assertions were too weak to notice.
    CRAWL_READERS = ["webcrawler", "compliance_auditor", "pci_scanner", "integration_advisor"]

    @staticmethod
    def _broken_state():
        """An EngineState whose crawl_result is the wrong type."""
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

    @pytest.mark.parametrize("module_name", CRAWL_READERS)
    async def test_agent_degrades_to_an_error_entry(self, module_name):
        """An agent that cannot do its work records why, instead of logging a success."""
        import importlib

        agent = importlib.import_module(f"backend.agents.{module_name}")
        update = await agent.run(self._broken_state())

        assert update.get("errors"), f"{module_name} recorded no error for an unusable crawl"
        assert update["audit_log"][0].result.startswith("ERROR:"), (
            f"{module_name} logged a success entry for a state it could not process: "
            f"{update['audit_log'][0].result}"
        )

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


class TestAuditLogAccumulatesOnce:
    """`audit_log` is an append-reducer channel, so a node must return only its own entry.

    ReportGenerator returned the whole accumulated list, which the reducer appended to what was
    already there, so the final state carried every agent twice. The report was built from a
    local variable and stayed correct, which is why nothing on screen ever showed it.

    Driven directly rather than through run_pipeline: the contract is about what the node
    returns, and an end-to-end version needed a served test site, which the unit CI job has no
    reason to provide.
    """

    @staticmethod
    def _state_with_history():
        from backend.models.schemas import AuditLogEntry, EngineState, MerchantInput

        state = EngineState(merchant_input=MerchantInput(
            website_url="https://example.com",
            pan_name="Acme Pvt. Ltd.", gst_legal_name="ACME PRIVATE LIMITED",
            bank_account_name="Acme Private Limited",
        ))
        state.audit_log = [
            AuditLogEntry(timestamp="2026-01-01T00:00:00", agent=name, action="a", result="r")
            for name in ("WebCrawler", "ComplianceAuditor", "PCIScanner", "KYCValidator",
                         "IntegrationAdvisor")
        ]
        return state

    async def test_report_generator_returns_only_its_own_entry(self):
        from backend.agents import report_generator

        state = self._state_with_history()
        update = await report_generator.run(state)

        agents = [e.agent for e in update["audit_log"]]
        assert agents == ["ReportGenerator"], (
            f"ReportGenerator returned {len(agents)} entries into an append-reducer channel, "
            f"which re-appends every earlier agent: {agents}"
        )

    async def test_report_carries_the_whole_trail(self):
        """Returning one entry must not shorten the trail the merchant sees."""
        from backend.agents import report_generator

        state = self._state_with_history()
        update = await report_generator.run(state)
        trail = [e.agent for e in update["readiness_report"].audit_trail]

        assert trail == [
            "WebCrawler", "ComplianceAuditor", "PCIScanner", "KYCValidator",
            "IntegrationAdvisor", "ReportGenerator",
        ], trail

    async def test_final_state_has_each_agent_once(self):
        """What the reducer produces, without needing a served site."""
        from backend.agents import report_generator

        state = self._state_with_history()
        update = await report_generator.run(state)
        merged = [e.agent for e in state.audit_log] + [e.agent for e in update["audit_log"]]

        duplicates = sorted({a for a in merged if merged.count(a) > 1})
        assert not duplicates, f"these agents would log more than once: {duplicates}"


class TestGapTitlesReadAsSentences:
    """A title cut at a fixed character count ended mid-word on screen.

    "PCI: 1 third-party social script(s) loaded (connect.facebook.net), review whether the" is
    what a reviewer saw in the demo. The full text is on the description; the title just has to
    stop somewhere sensible.
    """

    def test_a_long_message_stops_at_a_word(self):
        from backend.agents.report_generator import _headline

        message = (
            "1 third-party social script(s) loaded (connect.facebook.net), review whether they "
            "belong on a payment page (PCI 6.4.3)"
        )
        title = _headline(message)

        assert title.endswith("...")
        assert len(title) <= 83
        assert not title.rstrip(".").endswith(("the", "a", "of", "and", ","))
        # The word it stops on must be a whole word from the message.
        last = title.rstrip(".").rsplit(" ", 1)[-1]
        assert last in message.split(), f"{last!r} is not a whole word from the message"

    def test_a_short_message_is_untouched(self):
        from backend.agents.report_generator import _headline

        assert _headline("CSP header missing (PCI 11.6.1)") == "CSP header missing (PCI 11.6.1)"


class TestTheCrawlResultCarriesTheEntryUrl:
    """The crawler records where the homepage resolved to and the agent threw it away.

    `crawl_website` returns `entry_url`, `CrawlResult` declares it, and `webcrawler.run` built the
    model field by field without it, so every scan carried an empty string. The auditor needs it
    to tell the front page apart from the rest, and only kept working because it falls back to
    dict insertion order. A defensive default was hiding a real defect, which is the same shape as
    the bug this project exists to catch: declared in one place, not honoured by the code that
    runs.

    It matters most exactly where the fallback is weakest. A site that redirects to another domain
    has an entry URL that is not the one the merchant typed, and that is the value the report and
    the auditor both need.
    """

    @staticmethod
    def _serve_old_domain_redirecting_to_new():
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class NewHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"<!doctype html><html><body><h1>New home</h1></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        new = ThreadingHTTPServer(("127.0.0.1", 0), NewHandler)
        threading.Thread(target=new.serve_forever, daemon=True).start()
        new_port = new.server_address[1]

        class OldHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(301)
                self.send_header("Location", f"http://127.0.0.1:{new_port}{self.path}")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        old = ThreadingHTTPServer(("127.0.0.1", 0), OldHandler)
        threading.Thread(target=old.serve_forever, daemon=True).start()
        return old, new, old.server_address[1], new_port

    async def test_the_agent_records_where_the_homepage_actually_resolved(self):
        from backend.agents import webcrawler
        from backend.models.schemas import EngineState, MerchantInput

        old, new, old_port, new_port = self._serve_old_domain_redirecting_to_new()
        try:
            state = EngineState(
                merchant_input=MerchantInput(
                    website_url=f"http://127.0.0.1:{old_port}",
                    pan_name="Test Merchant Private Limited",
                    gst_legal_name="Test Merchant Private Limited",
                    bank_account_name="Test Merchant Private Limited",
                    business_type="ecommerce",
                )
            )
            result = await webcrawler.run(state)
        finally:
            for s in (old, new):
                s.shutdown()
                s.server_close()

        crawl = result["crawl_result"]
        assert crawl.entry_url, "the crawl result carried no entry URL at all"
        assert str(new_port) in crawl.entry_url, (
            f"the entry URL is the one the merchant typed, not where it resolved: "
            f"{crawl.entry_url}"
        )


class TestTheFourAnalysersAreRealGraphNodes:
    """The multi-agent claim has to be true in the graph, not only in the prose.

    The four analysers ran inside one `parallel_analysis` node via `asyncio.gather`. That is
    concurrent and it works, but the graph LangGraph compiles has a single node where the README
    diagram shows four, so anyone reading the code finds the architecture is narrated rather than
    built. The README also claimed this avoided LangGraph 0.2's fragile fan-out convergence, which
    was never measured: `asyncio.gather` is in the first commit of the pipeline, so it predates any
    fan-out ever being attempted.

    Fan-out is safe here and the state was already shaped for it. The four write four distinct
    result keys so no two ever write the same channel, `audit_log` and `errors` carry append
    reducers for the writes they do share, and none of them touches `current_phase`.
    """

    ANALYSERS = {"audit_compliance", "scan_pci", "validate_kyc", "advise_integration"}

    def test_each_analyser_is_its_own_node(self):
        from backend.agents.orchestrator import build_workflow

        nodes = set(build_workflow().get_graph().nodes)
        missing = self.ANALYSERS - nodes
        assert not missing, (
            f"the analysers are not separate nodes, so the graph does not fan out: missing "
            f"{sorted(missing)}. Nodes present: {sorted(nodes)}"
        )

    def test_the_crawl_fans_out_to_all_four(self):
        """Four branches leaving the crawl is what makes it parallel rather than sequential."""
        from backend.agents.orchestrator import build_workflow

        graph = build_workflow().get_graph()
        targets = {e.target for e in graph.edges if e.source == "crawl_website"}
        assert self.ANALYSERS <= targets, (
            f"the crawl does not branch to all four analysers, it goes to {sorted(targets)}"
        )

    def test_all_four_converge_before_the_report(self):
        """A join is what stops the report being written from a half-finished analysis."""
        from backend.agents.orchestrator import build_workflow

        graph = build_workflow().get_graph()
        for analyser in self.ANALYSERS:
            onward = {e.target for e in graph.edges if e.source == analyser}
            assert onward, f"{analyser} is a dead end, its result never reaches the report"


class TestFanOutPreservesHowTheAnalysersBehave:
    """Characterisation guards for the fan-out refactor: these pass before and after.

    Splitting one node into four must not quietly make the analysers sequential, and must not
    lose the graceful failure the pipeline already had, where one analyser breaking still leaves
    the other three in the report.
    """

    @staticmethod
    def _canned_crawl():
        return {
            "crawl_result": {
                "entry_url": "https://shop.example/",
                "pages_found": {"https://shop.example/": "<html><body><h1>Shop</h1></body></html>"},
                "scripts_found": [],
                "http_headers": {"https://shop.example/": {}},
                "identified_pages": {},
                "tech_stack_signals": {"static_html": ["none"]},
                "crawl_errors": [],
                "pages_crawled": 1,
            },
            "current_phase": "crawl_complete",
            "audit_log": [],
            "errors": [],
        }

    @staticmethod
    def _merchant_state():
        from backend.agents.orchestrator import _state_to_dict
        from backend.models.schemas import EngineState, MerchantInput

        return _state_to_dict(EngineState(merchant_input=MerchantInput(
            website_url="https://shop.example",
            pan_name="Artisan Weaves Private Limited",
            gst_legal_name="ARTISAN WEAVES PRIVATE LIMITED",
            bank_account_name="Artisan Weaves Private Limited",
            business_type="ecommerce",
        )))

    async def test_the_analysers_start_together_rather_than_in_turn(self, monkeypatch):
        """Four 0.4s analysers run in about 0.4s if parallel and about 1.6s if not."""
        import asyncio
        import time

        from backend.agents import (
            compliance_auditor, integration_advisor, kyc_validator, pci_scanner, webcrawler,
        )
        from backend.agents.orchestrator import build_workflow

        starts: list[float] = []

        def instrument(module, key):
            async def fake(state):
                starts.append(time.perf_counter())
                await asyncio.sleep(0.4)
                return {key: None, "audit_log": [], "errors": []}
            monkeypatch.setattr(module, "run", fake)

        for module, key in (
            (compliance_auditor, "compliance_result"), (pci_scanner, "pci_result"),
            (kyc_validator, "kyc_result"), (integration_advisor, "integration_result"),
        ):
            instrument(module, key)

        async def fake_crawl(state):
            return self._canned_crawl()

        monkeypatch.setattr(webcrawler, "run", fake_crawl)

        t0 = time.perf_counter()
        await build_workflow().ainvoke(self._merchant_state())
        elapsed = time.perf_counter() - t0

        assert len(starts) == 4, f"only {len(starts)} analysers ran"
        assert max(starts) - min(starts) < 0.3, (
            f"the analysers started {max(starts) - min(starts):.2f}s apart, so they are running "
            "one after another rather than together"
        )
        assert elapsed < 1.2, f"four 0.4s analysers took {elapsed:.2f}s, which is sequential"

    async def test_one_analyser_failing_leaves_the_other_three(self, monkeypatch):
        """Graceful failure is the property, and a node that raises must not take the graph down."""
        from backend.agents import (
            compliance_auditor, integration_advisor, kyc_validator, pci_scanner, webcrawler,
        )
        from backend.agents.orchestrator import build_workflow

        async def boom(state):
            raise RuntimeError("PCI scanner exploded")

        monkeypatch.setattr(pci_scanner, "run", boom)
        for module, key in (
            (compliance_auditor, "compliance_result"),
            (kyc_validator, "kyc_result"),
            (integration_advisor, "integration_result"),
        ):
            async def fake(state, _k=key):
                return {_k: None, "audit_log": [], "errors": []}
            monkeypatch.setattr(module, "run", fake)

        async def fake_crawl(state):
            return self._canned_crawl()

        monkeypatch.setattr(webcrawler, "run", fake_crawl)

        final = await build_workflow().ainvoke(self._merchant_state())

        assert any("PCI" in e or "pci" in e for e in final.get("errors", [])), (
            f"the failure was not recorded as an error: {final.get('errors')}"
        )
        assert final.get("readiness_report") is not None, (
            "one analyser raising took down the whole pipeline"
        )
