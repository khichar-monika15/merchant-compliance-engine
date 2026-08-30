"""The report assistant: answers a merchant's questions about their own scan.

A merchant who reads "PCI: CSP header missing" and does not know what a Content Security Policy
is gets nothing from the report. This closes that gap without weakening the claim the whole
project rests on, that every finding traces to a rule in a file:

* the checks are handed to the model as a digest built from `backend/knowledge/*.json`, so the
  rules it explains are the rules the engine applied, not the ones it remembers
* when the report is open, that merchant's actual findings go in too
* answers that come from the knowledge base cite the check id, and `cited_checks` reports which
  ones, so the UI can show which parts of an answer are grounded and which are not

Broader questions are allowed and are the reason the UI carries a disclaimer. The citation list
is what separates "this is your RBI-001 finding" from "this is the model talking".
"""
from __future__ import annotations

import logging
import re

from backend import knowledge
from backend.models.schemas import ReadinessReport

# Enough for an explanation with a worked fix, without inviting an essay.
logger = logging.getLogger(__name__)

_MAX_ANSWER_TOKENS = 700

# How many earlier turns to replay. The report digest dominates the prompt, so this stays small.
_MAX_HISTORY_TURNS = 6

_CHECK_ID = re.compile(r"\b(?:RBI|PCI)-\d{3}\b")

# Emphasis and headings the panel renders as literal characters.
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__", re.S)
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_BULLET = re.compile(r"^\s{0,3}[*+]\s+", re.M)


def strip_markdown(text: str) -> str:
    """Flatten markdown the chat panel would otherwise print as literal asterisks.

    The prompt asks for plain prose, and this project has already been bitten once by treating
    an instruction to the model as enforcement: the policy generator asked for placeholders to be
    replaced and shipped raw {{COMPANY_NAME}} to merchants when the model ignored it. Asking and
    then also doing it is idempotent and costs nothing.
    """
    text = _HEADING.sub("", text)
    text = _BOLD.sub(lambda m: m.group(1) or m.group(2), text)
    text = _ITALIC.sub(r"\1", text)
    text = _BULLET.sub("- ", text)
    return text.strip()


def known_check_ids() -> set[str]:
    return {c["id"] for c in knowledge.rbi_checks()} | {c["id"] for c in knowledge.pci_checks()}


def rule_digest() -> str:
    """Every check the engine applies, in the compact form a model can use.

    Built from the knowledge files rather than written out here, so a rule added to the checklist
    is a rule the assistant can explain, and one removed is one it stops claiming exists. The raw
    JSON is not used: it is mostly detection patterns the model has no use for.
    """
    lines: list[str] = []

    for check in knowledge.rbi_checks():
        parts = [
            f"{check['id']} ({check['category']}, {check['severity']}): {check['name']}",
            f"  What it requires: {check['description']}",
        ]
        scope = check.get("applies_to")
        if scope:
            parts.append(f"  Only applies to: {', '.join(scope)}")
        criteria = check.get("quality_criteria", {})
        if criteria.get("min_word_count"):
            parts.append(f"  A page under {criteria['min_word_count']} words counts as too thin.")
        topics = criteria.get("must_contain_topics")
        if topics:
            parts.append(f"  Must cover: {', '.join(topics)}")
        lines.append("\n".join(parts))

    for check in knowledge.pci_checks():
        scoring = check.get("scoring", {})
        parts = [
            f"{check['id']} (PCI DSS v4.0.1 requirement {check['requirement']}, "
            f"{check['severity']}): {check['name']}",
            f"  What it requires: {check['description']}",
        ]
        if scoring.get("max_points"):
            parts.append(f"  Worth up to {scoring['max_points']} of the 100 PCI points.")
        else:
            parts.append("  Raises warnings and carries no points.")
        for header in scoring.get("headers", []):
            parts.append(
                f"  {header['name']} is worth {header['points']} points "
                f"and must be: {header['requirement']}"
            )
        lines.append("\n".join(parts))

    return "\n\n".join(lines)


def report_digest(report: ReadinessReport | None) -> str:
    """This merchant's own result, so answers are about their site and not about compliance."""
    if report is None:
        return "The merchant has no scan open, so answer generally and say so."

    lines = [
        f"Overall score {report.overall_score} out of 100, grade {report.grade}.",
        f"Estimated time to fix: {report.estimated_fix_time}",
        "",
        "Score breakdown:",
    ]
    for component in report.score_breakdown:
        lines.append(f"  {component.label}: {component.score}/100, weighted {int(component.weight * 100)}%")

    for label, gaps in (("Critical gaps", report.critical_gaps), ("Warnings", report.warnings)):
        if not gaps:
            continue
        lines += ["", f"{label}:"]
        for gap in gaps:
            lines.append(f"  - {gap.title}")
            lines.append(f"    {gap.description}")
            if gap.fix_suggestion:
                lines.append(f"    Suggested fix: {gap.fix_suggestion}")
            if gap.source_url:
                lines.append(f"    Found on: {gap.source_url}")

    if report.compliance_details is not None:
        checks = {
            "Refund policy": report.compliance_details.refund_policy,
            "Privacy policy": report.compliance_details.privacy_policy,
            "Terms and conditions": report.compliance_details.terms_conditions,
            "Contact information": report.compliance_details.contact_info,
            "Shipping policy": report.compliance_details.shipping_policy,
            "GSTIN display": report.compliance_details.gst_display,
        }
        lines += ["", "Per-check results:"]
        for name, check in checks.items():
            if check is None:
                lines.append(f"  {name}: not applicable to this merchant")
                continue
            state = "found" if check.found else "not found"
            lines.append(f"  {name} ({check.check_id}): {state}, quality {check.quality_score}/10")

    return "\n".join(lines)


def build_prompt(
    question: str,
    report: ReadinessReport | None,
    history: list[dict] | None = None,
) -> str:
    """Assemble the grounded prompt. Kept separate from the call so a test can read it."""
    conversation = ""
    for turn in (history or [])[-_MAX_HISTORY_TURNS:]:
        role = "Merchant" if turn.get("role") == "user" else "Assistant"
        conversation += f"{role}: {turn.get('content', '')}\n"

    return f"""You are the compliance assistant inside MCIE, a tool that audits merchant websites
before they apply to a payment gateway in India. You are talking to the merchant about their own
scan.

THE CHECKS THIS ENGINE APPLIES
{rule_digest()}

THIS MERCHANT'S REPORT
{report_digest(report)}

HOW TO ANSWER
- Explain in plain English. The merchant is a business owner, not an engineer. Expand jargon the
  first time you use it, for example say Content Security Policy before saying CSP.
- When your answer comes from the checks above, name the check id in the answer, like RBI-001 or
  PCI-004. This is how the interface shows the merchant which part of the answer is grounded in a
  published rule.
- When the question goes beyond this merchant's report and the checks above, you may still answer
  from general knowledge, but say plainly that you are doing so and do not cite a check id for it.
- Never invent a check id, a points value or a regulation. If you do not know, say you do not know.
- Be brief. Three short paragraphs at most, and prefer fewer.
- Write plain prose. No markdown: no asterisks for emphasis, no headings, no bold. The panel
  shows your answer as plain text, so those characters appear literally.
- If they ask how to fix something, give the concrete step for their site.

{conversation}Merchant: {question}
Assistant:"""


def cited_checks(answer: str) -> list[str]:
    """The check ids an answer actually cites, filtered to ones that exist.

    A model that invents PCI-009 must not have it rendered as a citation, so this is an
    intersection with the knowledge base rather than a copy of whatever was matched.
    """
    known = known_check_ids()
    seen: list[str] = []
    for match in _CHECK_ID.findall(answer):
        if match in known and match not in seen:
            seen.append(match)
    return seen


def _reason_for(error: Exception) -> str:
    """A merchant-readable cause. The class name is the signal; the provider text is not."""
    name = type(error).__name__
    if "Authentication" in name or "PermissionDenied" in name:
        return "the model credential was rejected, it has most likely expired"
    if "RateLimit" in name:
        return "the model provider is rate limiting this key"
    if "Timeout" in name or "APIConnection" in name:
        return "the model endpoint could not be reached"
    return f"the model call failed ({name})"


def _unavailable(reason: str) -> str:
    """What the merchant sees when there is no model. Names the cause and what still works."""
    return (
        f"I cannot answer right now because {reason}. This is the only part of MCIE that needs a "
        "language model. Your report was produced without one, so every finding still has its "
        "rule and its suggested fix: open a finding in the report to see them."
    )


async def answer_question(
    question: str,
    report: ReadinessReport | None = None,
    history: list[dict] | None = None,
) -> dict:
    """Answer one question. Returns the answer plus which checks it is grounded in.

    A provider failure is an answer of its own, not a crash. This used to let the exception
    propagate, so the single most likely failure in practice, an expired credential, arrived at
    the merchant as a 500 and a generic "something went wrong". The `available` flag existed
    precisely to say what happened, and only covered the case where the provider returned an
    empty string.
    """
    from backend.tools.llm_client import llm_complete

    try:
        raw = await llm_complete(build_prompt(question, report, history), _MAX_ANSWER_TOKENS)
    except Exception as e:
        logger.warning("Assistant call failed: %s: %s", type(e).__name__, e)
        return {"answer": _unavailable(_reason_for(e)), "cited_checks": [], "available": False}

    text = strip_markdown(raw)

    if not text:
        # Configured but silent: llm_complete returns "" when nothing is configured at all, and a
        # provider can also answer with nothing.
        return {
            "answer": _unavailable("no language model is reachable"),
            "cited_checks": [],
            "available": False,
        }

    return {"answer": text, "cited_checks": cited_checks(text), "available": True}
