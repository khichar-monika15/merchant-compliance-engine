"""
Run all 4 test sites through the MCIE engine and validate against ground truth.
Usage: uv run python -m backend.tests.validate_ground_truth
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
            "website_url": "https://freshkart-india.vercel.app",
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
            "website_url": "https://artisan-weaves-test.vercel.app",
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
            "website_url": "https://clouddesk-test.vercel.app",
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
            "website_url": "https://quickbites-test.vercel.app",
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
