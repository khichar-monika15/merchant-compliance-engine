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
from backend.models.schemas import EngineState, MerchantInput


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
    return {"current_phase": "validated" if not errors else "error", "errors": errors}


async def _crawl(state: dict) -> dict:
    return _serialise(await webcrawler.run(_dict_to_state(state)))


async def _parallel_analysis(state: dict) -> dict:
    """Run compliance, PCI, KYC and integration concurrently, combining their partial updates."""
    s = _dict_to_state(state)
    agents = (compliance_auditor, pci_scanner, kyc_validator, integration_advisor)
    results = await asyncio.gather(*(a.run(s) for a in agents), return_exceptions=True)

    update: dict[str, Any] = {"current_phase": "parallel_complete", "audit_log": [], "errors": []}
    for agent, result in zip(agents, results):
        if isinstance(result, BaseException):
            # Each agent already handles its own errors, so reaching here means a genuine bug
            name = agent.__name__.rsplit(".", 1)[-1]
            update["errors"].append(f"{name} raised {type(result).__name__}: {result}")
            continue
        for key, value in _serialise(result).items():
            if key in ("audit_log", "errors"):
                update[key].extend(value)
            else:
                update[key] = value
    return update


async def _generate_policies(state: dict) -> dict:
    return _serialise(await policy_generator.run(_dict_to_state(state)))


async def _generate_report(state: dict) -> dict:
    return _serialise(await report_generator.run(_dict_to_state(state)))


def _route_after_crawl(state: dict) -> str:
    """Skip parallel analysis only when crawl failed entirely (no pages retrieved)."""
    crawl = state.get("crawl_result")
    crawl_pages = (crawl or {}).get("pages_found", {}) if isinstance(crawl, dict) else {}
    if state.get("current_phase") in ("error", "crawl_failed") and not crawl_pages:
        return "generate_report"
    return "parallel_analysis"


def _route_after_parallel(state: dict) -> str:
    """Run policy generation if compliance gaps exist."""
    compliance = state.get("compliance_result")
    if compliance is None:
        return "generate_report"

    checks = [
        compliance.get("refund_policy", {}),
        compliance.get("privacy_policy", {}),
        compliance.get("terms_conditions", {}),
    ]
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

    async def _emit(agent: str, message: str, pct: int, done: bool = False) -> None:
        if progress_fn:
            await progress_fn(agent, message, pct, done=done)

    async def _crawl_node(state: dict) -> dict:
        await _emit("WebCrawler", "Crawling merchant website", 15)
        result = await _crawl(state)
        await _emit("WebCrawler", "Website crawl complete", 30, done=True)
        return result

    async def _parallel_node(state: dict) -> dict:
        await _emit("ComplianceAuditor", "Auditing RBI policy compliance", 40)
        await _emit("PCIScanner", "Scanning PCI DSS surface", 40)
        await _emit("KYCValidator", "Validating KYC name consistency", 40)
        await _emit("IntegrationAdvisor", "Detecting tech stack", 40)
        result = await _parallel_analysis(state)
        await _emit("ComplianceAuditor", "Compliance audit complete", 60, done=True)
        await _emit("PCIScanner", "PCI DSS scan complete", 62, done=True)
        await _emit("KYCValidator", "KYC validation complete", 64, done=True)
        await _emit("IntegrationAdvisor", "Integration advisory complete", 65, done=True)
        return result

    async def _policies_node(state: dict) -> dict:
        await _emit("PolicyGenerator", "Generating missing policies", 75)
        result = await _generate_policies(state)
        await _emit("PolicyGenerator", "Policy generation complete", 85, done=True)
        return result

    async def _report_node(state: dict) -> dict:
        if not state.get("policy_gen_result"):
            await _emit("PolicyGenerator", "No policy gaps — generation skipped", 88, done=True)
        await _emit("ReportGenerator", "Generating readiness report", 90)
        result = await _generate_report(state)
        await _emit("ReportGenerator", "Report generation complete", 98, done=True)
        return result

    workflow = StateGraph(GraphState)
    workflow.add_node("validate_input", _validate_input)
    workflow.add_node("crawl_website", _crawl_node)
    workflow.add_node("parallel_analysis", _parallel_node)
    workflow.add_node("generate_policies", _policies_node)
    workflow.add_node("generate_report", _report_node)

    workflow.set_entry_point("validate_input")
    workflow.add_edge("validate_input", "crawl_website")

    workflow.add_conditional_edges(
        "crawl_website",
        _route_after_crawl,
        {"parallel_analysis": "parallel_analysis", "generate_report": "generate_report"},
    )

    workflow.add_conditional_edges(
        "parallel_analysis",
        _route_after_parallel,
        {"generate_policies": "generate_policies", "generate_report": "generate_report"},
    )

    workflow.add_edge("generate_policies", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


async def run_pipeline(merchant_input: MerchantInput, progress_fn=None) -> EngineState:
    """Run the full compliance pipeline for a merchant and return the final state."""
    app = build_workflow(progress_fn=progress_fn)
    initial_state = _state_to_dict(EngineState(merchant_input=merchant_input))
    final_state = await app.ainvoke(initial_state)
    return _dict_to_state(final_state)
