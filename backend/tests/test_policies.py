"""Policy drafts go straight to a merchant, so nothing template-shaped may survive into one.

The generation prompt instructs the model to "Replace all {{placeholder}} values". That was the
only thing enforcing it: a model that ignored the instruction produced a draft containing raw
{{COMPANY_NAME}}, and the code substituted placeholders only on the branch where the model
returned nothing at all.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.agents import policy_generator as pg
from backend.models.schemas import ComplianceCheck, ComplianceResult, EngineState, MerchantInput

_TEMPLATE_DIR = Path("backend/knowledge/policy_templates")
_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")

# policy_generator builds `needed` from exactly these three compliance checks.
POLICY_TYPES_THE_ENGINE_CAN_NEED = ("refund", "privacy", "terms", "shipping")


def _state(business_type: str = "ecommerce") -> EngineState:
    state = EngineState(
        merchant_input=MerchantInput(
            website_url="http://shop.example.com",
            pan_name="Example Retail Pvt. Ltd.",
            gst_legal_name="EXAMPLE RETAIL PRIVATE LIMITED",
            bank_account_name="Example Retail Private Limited",
            business_type=business_type,
        )
    )
    state.compliance_result = ComplianceResult(
        refund_policy=ComplianceCheck(name="Refund", check_id="RBI-001", found=False),
    )
    return state


class TestTemplatePlaceholders:
    def test_every_placeholder_has_a_replacement(self):
        """A template token with no replacement would ship to the merchant as-is."""
        declared = set()
        for path in _TEMPLATE_DIR.glob("*.md"):
            declared |= set(_PLACEHOLDER.findall(path.read_text(encoding="utf-8")))

        source = Path("backend/agents/policy_generator.py").read_text(encoding="utf-8")
        missing = sorted(t for t in declared if f'"{t}"' not in source)
        assert not missing, (
            f"policy templates use placeholders the generator never replaces: {missing}"
        )

    async def test_model_output_is_substituted_too(self, monkeypatch):
        """A model that ignores the instruction must not leak template tokens to a merchant."""

        async def lazy_llm(ptype, template, company, btype, url):
            return "# Policy\n\n{{COMPANY_NAME}} refunds within {{REFUND_PERIOD}} days."

        monkeypatch.setattr(pg, "_generate_with_llm", lazy_llm)
        update = await pg.run(_state())

        for policy in update["policy_gen_result"].generated_policies:
            leaked = _PLACEHOLDER.findall(policy.content)
            assert not leaked, f"{policy.policy_type} reached the merchant with {leaked}"

    async def test_template_fallback_is_substituted(self, monkeypatch):
        """The path that was already correct stays correct."""

        async def no_llm(ptype, template, company, btype, url):
            return ""

        monkeypatch.setattr(pg, "_generate_with_llm", no_llm)
        update = await pg.run(_state())

        for policy in update["policy_gen_result"].generated_policies:
            assert not _PLACEHOLDER.findall(policy.content), policy.policy_type
            # The generator uses the GST legal name, which is the one onboarding checks against.
            assert "EXAMPLE RETAIL PRIVATE LIMITED" in policy.content


class TestEveryTemplateIsReachable:
    """A template on disk that no policy type can select is a document we cannot produce."""

    def test_no_orphan_templates(self):
        """Reachability, not textual presence.

        Checking that a filename appears somewhere in the generator passed while
        shipping_ecommerce.md sat behind a branch no policy type could ever select. The engine
        only ever decides refund, privacy and terms are needed, so those are the inputs.
        """
        reachable = {
            pg._select_template(ptype, btype)
            for ptype in POLICY_TYPES_THE_ENGINE_CAN_NEED
            for btype in ("ecommerce", "saas", "services", "food_delivery", "unknown")
        }
        on_disk = {p.name for p in _TEMPLATE_DIR.glob("*.md")}
        orphans = sorted(on_disk - reachable)
        assert not orphans, (
            f"templates on disk no policy type can select: {orphans}. The engine ships them "
            f"and cannot produce them."
        )

    @pytest.mark.parametrize("policy_type", POLICY_TYPES_THE_ENGINE_CAN_NEED)
    @pytest.mark.parametrize("business_type", ["ecommerce", "saas", "services", "food_delivery"])
    def test_every_selectable_template_exists(self, policy_type, business_type):
        name = pg._select_template(policy_type, business_type)
        assert name, f"no template selected for {policy_type}/{business_type}"
        assert (_TEMPLATE_DIR / name).exists(), f"{name} is selected but not on disk"
