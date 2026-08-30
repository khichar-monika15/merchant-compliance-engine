from __future__ import annotations

import asyncio
import operator
from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from backend.agents import (
    compliance_auditor,
    integration_advisor,
    kyc_validator,
    policy_generator,
    report_generator,
    webcrawler,
    pci_scanner,
)
from backend.config import get_settings
from backend.models.schemas import EngineState, MerchantInput
from backend.tools.crawler_tools import url_refusal_reason


class GraphState(TypedDict, total=False):
    """Per-key channels for the pipeline.

    Declaring the keys individually is what makes a partial node return safe: LangGraph merges
    it into the existing state instead of replacing the whole state, which is what a bare
    `StateGraph(dict)` (a single `__root__` channel) would do. `audit_log` and `errors` use an
    append reducer so concurrent agents accumulate rather than overwrite each other.
    """
    merchant_input: dict
    crawl_result: Optional[dict]
    compliance_result: Optional[dict]
    pci_result: Optional[dict]
    kyc_result: Optional[dict]
    policy_gen_result: Optional[dict]
    integration_result: Optional[dict]
    readiness_report: Optional[dict]
    current_phase: str
    audit_log: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]


# LangGraph works on plain dicts; agents work on the validated EngineState
def _state_to_dict(state: EngineState) -> dict:
    return state.model_dump()


def _dict_to_state(d: dict) -> EngineState:
    return EngineState.model_validate(d)


# ── Node functions: each returns ONLY the keys it changed ─────────────────────

def _validate_input(state: dict) -> dict:
    inp = _dict_to_state(state).merchant_input
    errors = []
    if not str(inp.website_url).strip():
        errors.append("Website URL is required")
    if not inp.pan_name.strip():
        errors.append("PAN name is required")
    if not inp.gst_legal_name.strip():
        errors.append("GST legal name is required")
    if not inp.bank_account_name.strip():
        errors.append("Bank account name is required")

    # Refuse before a browser is launched: the crawler fetches whatever it is pointed at.
    refusal = url_refusal_reason(str(inp.website_url))
    if refusal:
        errors.append(f"Will not scan {inp.website_url}: {refusal}")

    return {"current_phase": "validated" if not errors else "error", "errors": errors}


async def _crawl(state: dict) -> dict:
    return _serialise(await webcrawler.run(_dict_to_state(state)))


# The four analysers, each its own branch of the graph. They fan out from the crawl and converge
# on `analysis_complete`, which is safe because no two of them write the same channel: each owns
# one result key, `audit_log` and `errors` carry append reducers for the writes they share, and
# none of them touches `current_phase`. That is set once at the join.
ANALYSERS: tuple[tuple[str, Any], ...] = (
    ("audit_compliance", compliance_auditor),
    ("scan_pci", pci_scanner),
    ("validate_kyc", kyc_validator),
    ("advise_integration", integration_advisor),
)


async def _run_analyser(agent, state: dict) -> dict:
    """One analyser as a graph node, holding on to the graceful failure the pipeline had.

    Every agent already catches its own exceptions and returns a partial state, so arriving in
    this except is a genuine bug in the agent rather than a scan that went wrong. It is still
    caught: a node that raises would abort the whole graph and lose the three analyses that
    succeeded, which is precisely the behaviour that must not change.
    """
    try:
        return _serialise(await agent.run(_dict_to_state(state)))
    except BaseException as e:  # noqa: BLE001 - deliberately broad, see docstring
        name = agent.__name__.rsplit(".", 1)[-1]
        return {"errors": [f"{name} raised {type(e).__name__}: {e}"], "audit_log": []}


async def _generate_policies(state: dict) -> dict:
    return _serialise(await policy_generator.run(_dict_to_state(state)))


async def _generate_report(state: dict) -> dict:
    return _serialise(await report_generator.run(_dict_to_state(state)))


def _route_after_crawl(state: dict) -> str:
    """Abort when the crawl retrieved nothing; a site we never reached cannot be graded.

    Playwright reports a refused connection through `crawl_errors` rather than by raising, so a
    total failure still arrives here looking like a successful crawl with an empty page set.
    Grading it produced a confident report for a site that does not exist.
    """
    crawl = state.get("crawl_result")
    crawl_pages = (crawl or {}).get("pages_found", {}) if isinstance(crawl, dict) else {}
    if not crawl_pages:
        return "abort"
    # A list fans out: LangGraph runs every named node in the same superstep.
    return [name for name, _ in ANALYSERS]


def _route_after_validate(state: dict) -> str:
    """Stop before crawling when the merchant details are unusable.

    `_validate_input` always computed these errors, but the edge to the crawler was unconditional,
    so three blank names produced a graded report whose KYC axis scored blank against blank as a
    clean match.
    """
    return "abort" if state.get("current_phase") == "error" else "crawl_website"


def _route_after_parallel(state: dict) -> str:
    """Run policy generation if compliance gaps exist."""
    compliance = state.get("compliance_result")
    if compliance is None:
        return "generate_report"

    # Every policy the generator can draft belongs here. Shipping was scored and gapped but never
    # routed, so a merchant whose only gap was shipping paid for it with the template unreachable.
    # `shipping_policy` is absent entirely when RBI-007 does not apply, which is not a gap.
    keys = ("refund_policy", "privacy_policy", "terms_conditions", "shipping_policy")
    checks = [c for c in (compliance.get(k) for k in keys) if c is not None]
    needs_policies = any(not c.get("found") or c.get("quality_score", 0) < 5 for c in checks)
    return "generate_policies" if needs_policies else "generate_report"


def _serialise(update: dict) -> dict:
    """Convert Pydantic models in update dict to plain dicts for LangGraph state."""
    result = {}
    for key, value in update.items():
        if hasattr(value, "model_dump"):
            result[key] = value.model_dump()
        elif isinstance(value, list):
            result[key] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def build_workflow(progress_fn=None):
    """Build and compile the LangGraph StateGraph for the MCIE pipeline."""

    async def _emit(
        agent: str, message: str, pct: int, done: bool = False, event_type: str = "progress"
    ) -> None:
        if progress_fn:
            await progress_fn(agent, message, pct, event_type=event_type, done=done)

    async def _crawl_node(state: dict) -> dict:
        await _emit("WebCrawler", "Crawling merchant website", 15)
        result = await _crawl(state)
        # Reporting "crawl complete" for a site that was never reached is the same false
        # confidence the pipeline used to show by grading it.
        if result.get("current_phase") == "crawl_failed":
            reason = (result.get("errors") or ["site unreachable"])[0]
            await _emit("WebCrawler", reason, -1, done=True, event_type="error")
            return result
        await _emit("WebCrawler", "Website crawl complete", 30, done=True)
        return result

    # Progress now belongs to the node that does the work, so the timeline reports each analyser
    # finishing when it actually finished rather than when the slowest of the four did.
    ANALYSER_PROGRESS = {
        "audit_compliance": ("ComplianceAuditor", "Auditing RBI policy compliance",
                             "Compliance audit complete", 60),
        "scan_pci": ("PCIScanner", "Scanning PCI DSS surface", "PCI DSS scan complete", 62),
        "validate_kyc": ("KYCValidator", "Validating KYC name consistency",
                         "KYC validation complete", 64),
        "advise_integration": ("IntegrationAdvisor", "Detecting tech stack",
                               "Integration advisory complete", 65),
    }

    def _analyser_node(node_name: str, agent):
        label, starting, finished, pct = ANALYSER_PROGRESS[node_name]

        async def node(state: dict) -> dict:
            await _emit(label, starting, 40)
            result = await _run_analyser(agent, state)
            await _emit(label, finished, pct, done=True)
            return result

        return node

    async def _analysis_complete(state: dict) -> dict:
        """The join. Nothing runs here; it exists so all four finish before routing decides."""
        return {"current_phase": "parallel_complete"}

    async def _policies_node(state: dict) -> dict:
        await _emit("PolicyGenerator", "Generating missing policies", 75)
        result = await _generate_policies(state)
        await _emit("PolicyGenerator", "Policy generation complete", 85, done=True)
        return result

    async def _report_node(state: dict) -> dict:
        if not state.get("policy_gen_result"):
            await _emit("PolicyGenerator", "No policy gaps, generation skipped", 88, done=True)
        await _emit("ReportGenerator", "Generating readiness report", 90)
        result = await _generate_report(state)
        await _emit("ReportGenerator", "Report generation complete", 98, done=True)
        return result

    workflow = StateGraph(GraphState)
    workflow.add_node("validate_input", _validate_input)
    workflow.add_node("crawl_website", _crawl_node)
    for node_name, agent in ANALYSERS:
        workflow.add_node(node_name, _analyser_node(node_name, agent))
    workflow.add_node("analysis_complete", _analysis_complete)
    workflow.add_node("generate_policies", _policies_node)
    workflow.add_node("generate_report", _report_node)

    workflow.set_entry_point("validate_input")
    workflow.add_conditional_edges(
        "validate_input",
        _route_after_validate,
        {"crawl_website": "crawl_website", "abort": END},
    )

    workflow.add_conditional_edges(
        "crawl_website",
        _route_after_crawl,
        {**{name: name for name, _ in ANALYSERS}, "abort": END},
    )

    # Every analyser leads to the join, so the report cannot be written from a half-finished
    # analysis: LangGraph waits for all four before `analysis_complete` runs.
    for node_name, _ in ANALYSERS:
        workflow.add_edge(node_name, "analysis_complete")

    workflow.add_conditional_edges(
        "analysis_complete",
        _route_after_parallel,
        {"generate_policies": "generate_policies", "generate_report": "generate_report"},
    )

    workflow.add_edge("generate_policies", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


async def run_pipeline(
    merchant_input: MerchantInput,
    progress_fn=None,
    timeout: float | None = None,
) -> EngineState:
    """Run the full compliance pipeline for a merchant and return the final state.

    A slow site or a stalled LLM must not pin a job at "running" forever, so the whole run is
    bounded. On timeout the caller still gets a valid EngineState carrying the error rather
    than an exception, so the API can report a failure with a reason.
    """
    if timeout is None:
        timeout = get_settings().pipeline_timeout

    app = build_workflow(progress_fn=progress_fn)
    initial_state = _state_to_dict(EngineState(merchant_input=merchant_input))

    try:
        final_state = await asyncio.wait_for(app.ainvoke(initial_state), timeout=timeout)
    except asyncio.TimeoutError:
        state = EngineState(merchant_input=merchant_input)
        state.current_phase = "error"
        state.errors = [f"Pipeline exceeded the {timeout:.0f}s time limit and was cancelled"]
        return state

    return _dict_to_state(final_state)
