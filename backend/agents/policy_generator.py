from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.tools.llm_client import llm_complete
from backend.models.schemas import (
    AuditLogEntry,
    EngineState,
    GeneratedPolicy,
    PolicyGenResult,
)

_TEMPLATES_DIR = Path(__file__).parent.parent / "knowledge" / "policy_templates"


def _load_template(filename: str) -> str:
    path = _TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _fill_template(template: str, replacements: dict) -> str:
    result = template
    for key, value in replacements.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def _select_template(policy_type: str, business_type: str) -> str:
    if policy_type == "refund":
        if business_type == "saas":
            return "refund_saas.md"
        if business_type == "services":
            return "refund_services.md"
        return "refund_ecommerce.md"
    if policy_type == "privacy":
        return "privacy_base.md"
    if policy_type == "terms":
        return "terms_base.md"
    if policy_type == "shipping":
        return "shipping_ecommerce.md"
    return ""


async def _generate_with_llm(
    policy_type: str,
    template: str,
    company_name: str,
    business_type: str,
    website_url: str,
) -> str:
    """Use LLM to customise the template for the merchant's specific context."""
    prompt = f"""You are a legal document specialist generating a {policy_type} policy for an Indian merchant.

Merchant details:
- Company name: {company_name}
- Business type: {business_type}
- Website: {website_url}

Base template (use as structure, customise to the merchant's business):
{template[:3000]}

Generate a complete, professional {policy_type} policy in Markdown. Replace all {{{{placeholder}}}} values with appropriate content based on the merchant details above. Make it specific to their business type. Keep it under 800 words. Output ONLY the Markdown document, no preamble."""

    return await llm_complete(prompt, max_tokens=2000)


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)

    try:
        compliance = state.compliance_result
        if compliance is None:
            return {"policy_gen_result": PolicyGenResult()}

        # Determine which policies are needed
        needed: list[str] = []
        checks = {
            "refund": compliance.refund_policy,
            "privacy": compliance.privacy_policy,
            "terms": compliance.terms_conditions,
        }
        for ptype, check in checks.items():
            if not check.found or check.quality_score < 5:
                needed.append(ptype)

        if not needed:
            return {
                "policy_gen_result": PolicyGenResult(policies_needed=[]),
                "audit_log": state.audit_log + [AuditLogEntry(
                    timestamp=t0.isoformat(),
                    agent="PolicyGenerator",
                    action="Policy generation check",
                    result="No policies need generation",
                )],
            }

        business_type = compliance.business_category or state.merchant_input.business_type or "ecommerce"
        company_name = state.merchant_input.gst_legal_name or state.merchant_input.pan_name
        website_url = str(state.merchant_input.website_url)

        # Basic replacements for template filling
        base_replacements = {
            "COMPANY_NAME": company_name,
            "COMPANY_ADDRESS": "[Your business address]",
            "CONTACT_EMAIL": "support@" + (website_url.split("//")[-1].split("/")[0] if website_url else "example.com"),
            "CONTACT_PHONE": "[Your phone number]",
            "LAST_UPDATED": datetime.now(timezone.utc).strftime("%B %Y"),
            "REFUND_PERIOD": "7",
            "WEBSITE_URL": website_url,
            "GST_NUMBER": "[Your GSTIN]",
            "JURISDICTION_CITY": "Bangalore",
            "STANDARD_SHIPPING_COST": "50",
            "EXPRESS_SHIPPING_COST": "150",
            "FREE_SHIPPING_THRESHOLD": "500",
        }

        generated: list[GeneratedPolicy] = []

        for ptype in needed:
            tmpl_file = _select_template(ptype, business_type)
            template = _load_template(tmpl_file)

            if template:
                content = await _generate_with_llm(ptype, template, company_name, business_type, website_url)
                if not content:
                    content = _fill_template(template, base_replacements)
            else:
                content = f"# {ptype.title()} Policy\n\n*Policy generation failed — template not found.*"

            generated.append(GeneratedPolicy(
                policy_type=ptype,
                content=content,
                tailored_to=business_type,
                word_count=len(content.split()),
            ))

        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="PolicyGenerator",
            action=f"Generated {len(generated)} policy documents",
            result=f"Generated: {', '.join(p.policy_type for p in generated)}",
            duration_ms=round(duration_ms, 1),
        )

        return {
            "policy_gen_result": PolicyGenResult(
                generated_policies=generated,
                policies_needed=needed,
            ),
            "audit_log": state.audit_log + [log],
        }

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="PolicyGenerator",
            action="Policy generation",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "errors": state.errors + [f"PolicyGenerator failed: {e}"],
            "audit_log": state.audit_log + [log],
        }
