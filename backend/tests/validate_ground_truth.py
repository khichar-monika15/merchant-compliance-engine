"""
Run all 4 test sites through the MCIE engine and validate against ground truth.

Serve the sites first, one per terminal:
    npx serve test-sites/freshkart-india      -p 4001
    npx serve test-sites/quickbites-delivery  -p 4002
    npx serve test-sites/clouddesk-saas       -p 4003
    npx serve test-sites/artisan-weaves       -p 4004

Then: uv run python -m backend.tests.validate_ground_truth
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.agents.orchestrator import run_pipeline
from backend.models.schemas import MerchantInput

_GT_DIR = Path(__file__).parent / "ground_truth"

TEST_CASES = [
    {
        "name": "FreshKart India (Grade F)",
        "gt_file": "freshkart_expected.json",
        "input": {
            "website_url": "http://127.0.0.1:4001",
            "pan_name": "FreshKart Pvt. Ltd.",
            "gst_legal_name": "FRESHKART PRIVATE LIMITED",
            "bank_account_name": "Fresh Kart Private Limited",
            "business_type": "ecommerce",
        },
    },
    {
        "name": "Artisan Weaves (Grade B)",
        "gt_file": "artisan_expected.json",
        "input": {
            "website_url": "http://127.0.0.1:4004",
            "pan_name": "Artisan Weaves Private Limited",
            "gst_legal_name": "ARTISAN WEAVES PRIVATE LIMITED",
            "bank_account_name": "Artisan Weaves Private Limited",
            "business_type": "ecommerce",
        },
    },
    {
        "name": "CloudDesk SaaS (Grade C)",
        "gt_file": "clouddesk_expected.json",
        "input": {
            "website_url": "http://127.0.0.1:4003",
            "pan_name": "CloudDesk Solutions Private Limited",
            "gst_legal_name": "CLOUDDESK SOLUTIONS PRIVATE LIMITED",
            "bank_account_name": "CloudDesk Solutions Private Limited",
            "business_type": "saas",
        },
    },
    {
        "name": "QuickBites Delivery (Grade D)",
        "gt_file": "quickbites_expected.json",
        "input": {
            "website_url": "http://127.0.0.1:4002",
            "pan_name": "QuickBites Pvt. Ltd.",
            "gst_legal_name": "QUICKBITES PRIVATE LIMITED",
            "bank_account_name": "Quick Bites Private Limited",
            "business_type": "food_delivery",
        },
    },
]


def _check(label: str, condition: bool, actual, expected) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}: actual={actual!r}, expected={expected!r}")
    return condition


async def validate_one(tc: dict) -> bool:
    print(f"\n{'='*60}")
    print(f"Testing: {tc['name']}")
    print(f"{'='*60}")

    gt = json.loads((_GT_DIR / tc["gt_file"]).read_text())
    merchant = MerchantInput(**tc["input"])

    state = await run_pipeline(merchant)
    report = state.readiness_report

    if not report:
        print("  [FAIL] No report generated")
        return False

    passed = 0
    total = 0

    # Score range
    lo, hi = gt["expected_score_range"]
    ok = lo <= report.overall_score <= hi
    total += 1
    passed += int(_check("Score in range", ok, report.overall_score, f"{lo}-{hi}"))

    # Grade
    total += 1
    passed += int(_check("Grade", report.grade == gt["expected_grade"], report.grade, gt["expected_grade"]))

    # KYC
    kyc_exp = gt.get("kyc_expected", {})
    if state.kyc_result and "overall_consistent" in kyc_exp:
        total += 1
        passed += int(_check("KYC consistent", state.kyc_result.overall_consistent == kyc_exp["overall_consistent"],
                             state.kyc_result.overall_consistent, kyc_exp["overall_consistent"]))

    # Critical gap count
    if "critical_gaps_min" in gt:
        total += 1
        passed += int(_check("Critical gaps (min)", len(report.critical_gaps) >= gt["critical_gaps_min"],
                             len(report.critical_gaps), f">= {gt['critical_gaps_min']}"))

    if "critical_gaps_max" in gt:
        total += 1
        passed += int(_check("Critical gaps (max)", len(report.critical_gaps) <= gt["critical_gaps_max"],
                             len(report.critical_gaps), f"<= {gt['critical_gaps_max']}"))

    if "issues_max_count" in kyc_exp and state.kyc_result:
        total += 1
        n = len(state.kyc_result.common_mismatches)
        passed += int(_check("KYC issues (max)", n <= kyc_exp["issues_max_count"], n, f"<= {kyc_exp['issues_max_count']}"))

    if "issues_min_count" in kyc_exp and state.kyc_result:
        total += 1
        n = len(state.kyc_result.common_mismatches)
        passed += int(_check("KYC issues (min)", n >= kyc_exp["issues_min_count"], n, f">= {kyc_exp['issues_min_count']}"))

    # Per-check RBI expectations
    checks = {
        "refund_policy": state.compliance_result.refund_policy if state.compliance_result else None,
        "privacy_policy": state.compliance_result.privacy_policy if state.compliance_result else None,
        "terms_conditions": state.compliance_result.terms_conditions if state.compliance_result else None,
        "contact_info": state.compliance_result.contact_info if state.compliance_result else None,
        "gst_display": state.compliance_result.gst_display if state.compliance_result else None,
    }
    for key, expected in gt.get("compliance_expected", {}).items():
        check = checks.get(key)
        if check is None:
            continue
        if "found" in expected:
            total += 1
            passed += int(_check(f"{key}.found", check.found == expected["found"], check.found, expected["found"]))
        if "quality_score_min" in expected:
            total += 1
            passed += int(_check(f"{key}.quality>=", check.quality_score >= expected["quality_score_min"],
                                 check.quality_score, f">= {expected['quality_score_min']}"))
        if "quality_score_max" in expected:
            total += 1
            passed += int(_check(f"{key}.quality<=", check.quality_score <= expected["quality_score_max"],
                                 check.quality_score, f"<= {expected['quality_score_max']}"))

    # PCI expectations
    pci_exp = gt.get("pci_expected", {})
    pci = state.pci_result
    if pci:
        counts = {
            "total_scripts": pci.total_scripts,
            "third_party_scripts": pci.third_party_scripts,
            "scripts_without_sri": pci.scripts_without_sri,
        }
        for name, actual in counts.items():
            if f"{name}_max" in pci_exp:
                total += 1
                bound = pci_exp[f"{name}_max"]
                passed += int(_check(f"{name}_max", actual <= bound, actual, f"<= {bound}"))
            if f"{name}_min" in pci_exp:
                total += 1
                bound = pci_exp[f"{name}_min"]
                passed += int(_check(f"{name}_min", actual >= bound, actual, f">= {bound}"))

        presence = {
            "csp_present": pci.csp_header.get("present", False),
            "hsts_present": pci.hsts_header.get("present", False),
            "referrer_policy_present": pci.referrer_policy.get("present", False),
        }
        for key, actual in presence.items():
            if key in pci_exp:
                total += 1
                passed += int(_check(key, actual == pci_exp[key], actual, pci_exp[key]))

    print(f"\n  Result: {passed}/{total} checks passed")
    return passed == total


async def main():
    results = []
    for tc in TEST_CASES:
        ok = await validate_one(tc)
        results.append((tc["name"], ok))

    print(f"\n{'='*60}")
    print("GROUND TRUTH VALIDATION SUMMARY")
    print(f"{'='*60}")
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    total_passed = sum(1 for _, ok in results if ok)
    print(f"\n{total_passed}/{len(results)} test sites passed")


if __name__ == "__main__":
    asyncio.run(main())
