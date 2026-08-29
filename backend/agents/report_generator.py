from __future__ import annotations

from datetime import datetime, timezone

from backend.models.schemas import (
    AuditLogEntry,
    EngineState,
    GapItem,
    ReadinessReport,
    ScoreComponent,
    Severity,
)

# Scoring weights
_WEIGHTS = {
    "rbi_compliance": 0.40,
    "kyc": 0.25,
    "pci": 0.20,
    "integration": 0.15,
}

_GRADE_THRESHOLDS = [(90, "A"), (75, "B"), (50, "C"), (25, "D"), (0, "F")]


def _score_to_grade(score: int) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _kyc_score(kyc) -> int:
    """Score on how many of the three document pairs agree.

    Fuzzy similarity alone is useless here: 'FreshKart Pvt. Ltd.' and 'Fresh Kart Private
    Limited' are 0.98 similar but are a genuine onboarding blocker, so a name mismatch has to
    cost the merchant real points.
    """
    if kyc is None:
        return 0
    if kyc.overall_consistent:
        return 100

    pairs = [kyc.pan_gst_match, kyc.gst_bank_match, kyc.pan_bank_match]
    matching = sum(1 for p in pairs if p.match)
    # Partial credit for how close the failing pairs are, capped below a clean pass
    closeness = sum(p.similarity for p in pairs if not p.match) / len(pairs)
    return min(90, int((matching / len(pairs)) * 100 + closeness * 10))


def _integration_score(integration) -> int:
    """Readiness to integrate. A live test order is a bonus, not a gate — a merchant is not
    penalised because the operator has no Razorpay keys configured."""
    if integration is None:
        return 0
    score = 70 if (integration.detected_stack and integration.starter_code) else 40
    if integration.test_payment_result.get("success"):
        score += 30
    return min(100, score)


def _estimate_fix_time(critical: int, warnings: int) -> str:
    if critical == 0 and warnings == 0:
        return "No fixes needed — ready for Razorpay onboarding"
    if critical == 0:
        return "1–2 hours (minor improvements only)"
    if critical <= 2:
        return "1–2 days (add missing policies, fix contact info)"
    if critical <= 4:
        return "3–5 days (multiple policy documents needed, KYC alignment required)"
    return "1–2 weeks (major compliance overhaul required)"


def _compliance_gaps(compliance) -> tuple[list[GapItem], list[GapItem], list[GapItem]]:
    critical, warnings, info = [], [], []
    if compliance is None:
        return critical, warnings, info

    checks = {
        "refund": compliance.refund_policy,
        "privacy": compliance.privacy_policy,
        "terms": compliance.terms_conditions,
        "contact": compliance.contact_info,
        "gst": compliance.gst_display,
    }
    fix_hints = {
        "refund": "Add a Refund & Returns Policy page covering timeline, eligibility, and process",
        "privacy": "Add a Privacy Policy covering data collection, DPDP Act 2023 compliance, and user rights",
        "terms": "Add Terms & Conditions with Indian governing law and payment terms",
        "contact": "Add a Contact page with physical Indian address, phone number, and email",
        "gst": "Display your GSTIN in the website footer or About page",
    }

    for key, check in checks.items():
        if check.found and check.quality_score >= 7:
            continue
        gap = GapItem(
            title=f"{'Missing' if not check.found else 'Inadequate'}: {check.name}",
            description="; ".join(check.issues) if check.issues else f"{check.name} not found or too thin",
            severity=check.severity,
            category="compliance",
            fix_suggestion=fix_hints.get(key, ""),
        )
        if check.severity == Severity.CRITICAL:
            critical.append(gap)
        elif check.severity == Severity.WARNING:
            warnings.append(gap)
        else:
            info.append(gap)

    return critical, warnings, info


def _pci_gaps(pci) -> tuple[list[GapItem], list[GapItem], list[GapItem]]:
    critical, warnings, info = [], [], []
    if pci is None:
        return critical, warnings, info

    # Severity follows the knowledge base: PCI-001/002/004 are critical, PCI-005 (header suite) is a warning
    for issue in pci.critical_issues:
        sev = Severity.CRITICAL if any(kw in issue.lower() for kw in ["csp", "sri", "6.4.3"]) else Severity.WARNING
        gap = GapItem(
            title=f"PCI: {issue[:80]}",
            description=issue,
            severity=sev,
            category="pci",
            fix_suggestion="See PCI DSS v4.0.1 Requirements 6.4.3 and 11.6.1",
        )
        (critical if sev == Severity.CRITICAL else warnings).append(gap)

    return critical, warnings, info


def _kyc_gaps(kyc) -> tuple[list[GapItem], list[GapItem], list[GapItem]]:
    critical, warnings, info = [], [], []
    if kyc is None or kyc.overall_consistent:
        return critical, warnings, info

    for mismatch in kyc.common_mismatches:
        critical.append(GapItem(
            title=f"KYC mismatch: {mismatch}",
            description=mismatch,
            severity=Severity.CRITICAL,
            category="kyc",
            fix_suggestion="Ensure the business name is identical across PAN certificate, GST registration, and bank account — resolve abbreviation differences like Pvt./Private and Ltd./Limited",
        ))

    return critical, warnings, info


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)

    try:
        # Gather component scores
        rbi_score = state.compliance_result.overall_score if state.compliance_result else 0
        kyc_score = _kyc_score(state.kyc_result)
        pci_score = state.pci_result.security_score if state.pci_result else 0
        integration_score = _integration_score(state.integration_result)

        # Weighted score. The breakdown ships with the report so the UI renders the numbers
        # the backend actually used instead of recomputing them and drifting.
        breakdown = [
            ScoreComponent(label="RBI Compliance", score=rbi_score, weight=_WEIGHTS["rbi_compliance"]),
            ScoreComponent(label="KYC Consistency", score=kyc_score, weight=_WEIGHTS["kyc"]),
            ScoreComponent(label="PCI DSS", score=pci_score, weight=_WEIGHTS["pci"]),
            ScoreComponent(label="Integration", score=integration_score, weight=_WEIGHTS["integration"]),
        ]
        overall = int(sum(c.score * c.weight for c in breakdown))
        grade = _score_to_grade(overall)

        # Collect all gaps
        c_comp, w_comp, i_comp = _compliance_gaps(state.compliance_result)
        c_pci, w_pci, i_pci = _pci_gaps(state.pci_result)
        c_kyc, w_kyc, i_kyc = _kyc_gaps(state.kyc_result)

        all_critical = c_comp + c_pci + c_kyc
        all_warnings = w_comp + w_pci + w_kyc
        all_info = i_comp + i_pci + i_kyc

        fix_time = _estimate_fix_time(len(all_critical), len(all_warnings))

        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="ReportGenerator",
            action="Aggregate readiness report",
            result=f"Score {overall}/100 | Grade {grade} | {len(all_critical)} critical, {len(all_warnings)} warnings",
            duration_ms=round(duration_ms, 1),
        )
        final_audit_log = state.audit_log + [log]

        report = ReadinessReport(
            overall_score=overall,
            grade=grade,
            score_breakdown=breakdown,
            critical_gaps=all_critical,
            warnings=all_warnings,
            info_items=all_info,
            compliance_details=state.compliance_result,
            pci_details=state.pci_result,
            kyc_details=state.kyc_result,
            generated_policies=state.policy_gen_result,
            integration_details=state.integration_result,
            estimated_fix_time=fix_time,
            audit_trail=final_audit_log,
        )

        return {
            "readiness_report": report,
            "current_phase": "complete",
            "audit_log": final_audit_log,
        }

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="ReportGenerator",
            action="Report generation",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "errors": [f"ReportGenerator failed: {e}"],
            "current_phase": "error",
            "audit_log": [log],
        }
