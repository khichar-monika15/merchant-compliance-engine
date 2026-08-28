"""End-to-end smoke run against artisan-weaves (Grade B expected).

Serve the site first:  npx serve test-sites/artisan-weaves -p 4004
Then:                  uv run python -m backend.tests.e2e_artisan
"""
import asyncio

from backend.agents.orchestrator import run_pipeline
from backend.models.schemas import MerchantInput


async def main():
    merchant = MerchantInput(
        website_url="http://127.0.0.1:4004",
        pan_name="Artisan Weaves Private Limited",
        gst_legal_name="ARTISAN WEAVES PRIVATE LIMITED",
        bank_account_name="Artisan Weaves Private Limited",
        business_type="ecommerce",
    )

    print("Starting pipeline...")
    report = await run_pipeline(merchant)
    # run_pipeline returns EngineState; readiness_report is nested inside
    rr = report.readiness_report
    if rr is None:
        print("ERROR: No readiness_report in final state")
        print("Compliance:", report.compliance_result)
        print("Errors:", report.errors)
        return
    print(f"\nScore: {rr.overall_score}/100  Grade: {rr.grade}")
    rbi = report.compliance_result
    pci = report.pci_result
    kyc = report.kyc_result
    print(f"RBI:  {rbi.overall_score if rbi else 'N/A'}")
    print(f"PCI:  {pci.security_score if pci else 'N/A'}")
    print(f"KYC:  consistent={kyc.overall_consistent if kyc else 'N/A'}")
    if rbi:
        checks = [rbi.refund_policy, rbi.privacy_policy, rbi.terms_conditions, rbi.contact_info, rbi.gst_display]
        for c in checks:
            print(f"  [{c.check_id}] {c.name}: found={c.found} quality={c.quality_score}")
    all_gaps = (rr.critical_gaps or []) + (rr.warnings or [])
    print(f"\nGaps — critical={len(rr.critical_gaps or [])}, warnings={len(rr.warnings or [])}")
    for g in all_gaps[:4]:
        print(f"  [{g.severity}] {g.description[:60]}")
    print(f"Audit log: {len(report.audit_log)} entries")
    print(f"Fix time: {rr.estimated_fix_time}")


if __name__ == "__main__":
    asyncio.run(main())
