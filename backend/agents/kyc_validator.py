from __future__ import annotations

from datetime import datetime, timezone

from backend.models.schemas import AuditLogEntry, EngineState, KYCMatch, KYCResult
from backend.tools.name_matcher import validate_kyc_consistency


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)
    inp = state.merchant_input

    try:
        raw = validate_kyc_consistency(
            inp.pan_name,
            inp.gst_legal_name,
            inp.bank_account_name,
        )

        kyc_result = KYCResult(
            pan_gst_match=KYCMatch(**raw["pan_gst_match"]),
            gst_bank_match=KYCMatch(**raw["gst_bank_match"]),
            pan_bank_match=KYCMatch(**raw["pan_bank_match"]),
            common_mismatches=raw["common_mismatches"],
            overall_consistent=raw["overall_consistent"],
            confidence=raw["confidence"],
        )

        summary = "PASS" if kyc_result.overall_consistent else f"FAIL — {len(kyc_result.common_mismatches)} mismatches"
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="KYCValidator",
            action=f"Validated KYC names for '{inp.pan_name}'",
            result=summary,
            duration_ms=round(duration_ms, 1),
        )

        return {
            "kyc_result": kyc_result,
            "audit_log": state.audit_log + [log],
        }

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="KYCValidator",
            action="KYC validation",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "errors": state.errors + [f"KYCValidator failed: {e}"],
            "audit_log": state.audit_log + [log],
        }
