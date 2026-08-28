from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.models.schemas import AuditLogEntry, EngineState, IntegrationResult
from backend.tools.razorpay_client import create_order

_STACKS_DB_PATH = Path(__file__).parent.parent / "knowledge" / "tech_stack_signatures.json"
_STARTER_DIR = Path(__file__).parent.parent / "knowledge" / "starter_code_templates"


def _load_stacks_db() -> dict:
    with _STACKS_DB_PATH.open() as f:
        return json.load(f)


def _pick_primary_stack(tech_signals: dict[str, list[str]]) -> str:
    """Return the highest-confidence detected stack."""
    priority = ["shopify", "woocommerce", "nextjs", "django", "laravel", "react", "vue_nuxt", "static_html"]
    for stack in priority:
        if stack in tech_signals:
            return stack
    if tech_signals:
        return next(iter(tech_signals))
    return "static_html"


def _load_starter_code(filename: str) -> tuple[str, str]:
    """Return (code, language_label)."""
    path = _STARTER_DIR / filename
    if not path.exists():
        return "", "text"
    code = path.read_text(encoding="utf-8")
    ext = path.suffix.lstrip(".")
    lang_map = {"tsx": "typescript", "vue": "vue", "py": "python", "php": "php", "html": "html", "md": "markdown"}
    return code, lang_map.get(ext, ext)


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)

    try:
        crawl = state.crawl_result
        tech_signals = crawl.tech_stack_signals if crawl else {}
        stacks_db = _load_stacks_db()["stacks"]

        primary_stack = _pick_primary_stack(tech_signals)
        stack_info = stacks_db.get(primary_stack, stacks_db["static_html"])
        rec = stack_info["razorpay_recommendation"]

        starter_file = rec.get("starter_template", "html_razorpay.html")
        starter_code, lang = _load_starter_code(starter_file)

        # Run a test payment on Razorpay test-mode
        test_payment = create_order(amount_paise=100, notes={"purpose": "MCIE integration test"})

        result = IntegrationResult(
            detected_stack={
                "primary": primary_stack,
                "evidence": tech_signals.get(primary_stack, []),
                "all_detected": list(tech_signals.keys()),
            },
            recommended_product=rec.get("product", "Razorpay Standard Checkout"),
            integration_method=rec.get("integration_method", "standard_checkout"),
            starter_code=starter_code,
            starter_code_language=lang,
            test_payment_result=test_payment,
        )

        test_status = "PASS" if test_payment.get("success") else f"FAIL ({test_payment.get('error', 'unknown')})"
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="IntegrationAdvisor",
            action=f"Tech stack detection + Razorpay integration recommendation",
            result=f"Detected: {primary_stack} → Recommend: {rec['product']} | Test payment: {test_status}",
            duration_ms=round(duration_ms, 1),
        )

        return {
            "integration_result": result,
            "audit_log": state.audit_log + [log],
        }

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="IntegrationAdvisor",
            action="Integration advisory",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "errors": state.errors + [f"IntegrationAdvisor failed: {e}"],
            "audit_log": state.audit_log + [log],
        }
