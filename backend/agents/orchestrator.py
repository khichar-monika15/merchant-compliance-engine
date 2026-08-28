from __future__ import annotations

import asyncio
from typing import Any

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
from backend.models.schemas import AuditLogEntry, EngineState, MerchantInput


# LangGraph requires state as a plain dict or TypedDict; we adapt EngineState
def _state_to_dict(state: EngineState) -> dict:
    return state.model_dump()


def _dict_to_state(d: dict) -> EngineState:
    return EngineState.model_validate(d)


def _merge_state(current: dict, update: dict) -> dict:
    """Merge partial state update dict into current state dict."""
    merged = current.copy()
    for key, value in update.items():
        if key == "audit_log" and isinstance(value, list):
            merged[key] = value  # already cumulative from agents
        elif key == "errors" and isinstance(value, list):
            merged[key] = value
        else:
            merged[key] = value
    return merged


# ── Node functions (LangGraph expects plain dict → dict) ──────────────────────

def _validate_input(state: dict) -> dict:
    s = _dict_to_state(state)
    inp = s.merchant_input
    errors = []
    if not str(inp.website_url).strip():
        errors.append("Website URL is required")
    if not inp.pan_name.strip():
        errors.append("PAN name is required")
    if not inp.gst_legal_name.strip():
        errors.append("GST legal name is required")
    if not inp.bank_account_name.strip():
        errors.append("Bank account name is required")
    update = {
        "current_phase": "validated" if not errors else "error",
        "errors": s.errors + errors,
    }
    return _merge_state(state, update)


async def _crawl(state: dict) -> dict:
    s = _dict_to_state(state)
    update = await webcrawler.run(s)
    return _merge_state(state, _serialise(update))


async def _parallel_analysis(state: dict) -> dict:
    """Run compliance, PCI, KYC, and integration agents concurrently."""
    s = _dict_to_state(state)
    results = await asyncio.gather(
        compliance_auditor.run(s),
        pci_scanner.run(s),
        kyc_validator.run(s),
        integration_advisor.run(s),
        return_exceptions=True,
    )

    merged = state.copy()
    combined_log = list(state.get("audit_log", []))
    combined_errors = list(state.get("errors", []))

    for result in results:
        if isinstance(result, Exception):
            combined_errors.append(str(result))
        elif isinstance(result, dict):
            serialised = _serialise(result)
            for key, value in serialised.items():
                if key == "audit_log":
                    # audit_log from each agent includes prior entries — take the last one's additions
                    new_entries = [e for e in value if e not in combined_log]
                    combined_log.extend(new_entries)
                elif key == "errors":
                    combined_errors.extend(v for v in value if v not in combined_errors)
                else:
                    merged[key] = value

    merged["audit_log"] = combined_log
    merged["errors"] = combined_errors
    merged["current_phase"] = "parallel_complete"
    return merged


async def _generate_policies(state: dict) -> dict:
    s = _dict_to_state(state)
    update = await policy_generator.run(s)
    return _merge_state(state, _serialise(update))


async def _generate_report(state: dict) -> dict:
    s = _dict_to_state(state)
    update = await report_generator.run(s)
    return _merge_state(state, _serialise(update))


def _route_after_crawl(state: dict) -> str:
    """Skip parallel analysis only if a fatal crawl error occurred AND no URL was reachable."""
    if state.get("current_phase") == "error":
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


def build_workflow():
    """Build and compile the LangGraph StateGraph for the MCIE pipeline."""
    # Use plain dict as state type (LangGraph 0.2.x compatible)
    workflow = StateGraph(dict)

    workflow.add_node("validate_input", _validate_input)
    workflow.add_node("crawl_website", _crawl)
    workflow.add_node("parallel_analysis", _parallel_analysis)
    workflow.add_node("generate_policies", _generate_policies)
    workflow.add_node("generate_report", _generate_report)

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


async def run_pipeline(merchant_input: MerchantInput) -> EngineState:
    """Run the full compliance pipeline for a merchant and return the final state."""
    app = build_workflow()
    initial_state = _state_to_dict(EngineState(merchant_input=merchant_input))
    final_state = await app.ainvoke(initial_state)
    return _dict_to_state(final_state)
