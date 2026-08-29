"""
Run all 4 test sites through the MCIE engine and validate against ground truth.

The bounds in `ground_truth/*.json` are set to hold on BOTH paths, rule-based scoring with no
credentials and LLM-refined scoring with them. The LLM moves individual policy quality scores by a
point or two and the totals with them, but no grade changes. Widen a bound only after measuring
both ways, never to make a run go green.

One invocation exercises one path, whichever the environment supplies. Checking both means running
it twice, and the banner below reports which path actually ran so a transcript cannot be mistaken
for the other one.

Serve the sites first, one per terminal:
    npx serve test-sites/freshkart-india      -p 4001
    npx serve test-sites/quickbites-delivery  -p 4002
    npx serve test-sites/clouddesk-saas       -p 4003
    npx serve test-sites/artisan-weaves       -p 4004

Then, for the LLM path:
    uv run python -m backend.tests.validate_ground_truth

And for the rule-only path:
    env OPENAI_API_KEY="" ANTHROPIC_API_KEY="" uv run python -m backend.tests.validate_ground_truth

Exits non-zero if any site fails, so it can gate a build.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from backend.agents.orchestrator import run_pipeline
from backend.models.schemas import MerchantInput

_GT_DIR = Path(__file__).parent / "ground_truth"

TEST_CASES = [
    ("FreshKart India (Grade F)", "freshkart_expected.json"),
    ("Artisan Weaves (Grade B)", "artisan_expected.json"),
    ("CloudDesk SaaS (Grade C)", "clouddesk_expected.json"),
    ("QuickBites Delivery (Grade D)", "quickbites_expected.json"),
]


def _merchant_from(gt: dict) -> MerchantInput:
    """The fixture is the single source of truth for the merchant under test.

    The URL, the three KYC names and the business type used to be duplicated here, so a fixture
    could be edited without changing what was actually scanned.
    """
    kyc = gt["kyc_input"]
    return MerchantInput(
        website_url=gt["served_on"],
        pan_name=kyc["pan_name"],
        gst_legal_name=kyc["gst_name"],
        bank_account_name=kyc["bank_name"],
        business_type=gt["business_type"],
    )


def _check(label: str, condition: bool, actual, expected) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}: actual={actual!r}, expected={expected!r}")
    return condition


async def validate_one(name: str, gt_file: str, rule_path: bool = False) -> bool:
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    gt = json.loads((_GT_DIR / gt_file).read_text())
    merchant = _merchant_from(gt)

    state = await run_pipeline(merchant)
    report = state.readiness_report

    if not report:
        print("  [FAIL] No report generated")
        return False

    passed = 0
    total = 0

    # Score range. The band is wide enough to hold either scoring path, so on the rule path,
    # which is deterministic, the exact value is asserted instead. A band 15 points wide cannot
    # notice a two point drift, and that is exactly how a stale demo score survived.
    lo, hi = gt["expected_score_range"]
    ok = lo <= report.overall_score <= hi
    total += 1
    passed += int(_check("Score in range", ok, report.overall_score, f"{lo}-{hi}"))

    if rule_path and "measured_score_rule_path" in gt:
        exact = gt["measured_score_rule_path"]
        total += 1
        passed += int(_check(
            "Score exactly matches the recorded rule-path value",
            report.overall_score == exact, report.overall_score, exact,
        ))

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
        # None when RBI-007 does not apply to this merchant, which is a real outcome rather
        # than a missing value.
        "shipping_policy": state.compliance_result.shipping_policy if state.compliance_result else None,
    }
    for key, expected in gt.get("compliance_expected", {}).items():
        if key not in checks:
            # A fixture key the harness does not map used to be skipped in silence, so a typo
            # disabled the assertion without anyone noticing.
            raise KeyError(
                f"{key!r} is expected in ground truth but the harness maps no check for it"
            )
        check = checks[key]
        if check is None:
            print(f"    [SKIP] {key}: not applicable to this merchant")
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
            # Pinned so a change to header scoring shows up here rather than only in the total,
            # where a 20% weight can hide it.
            "security_score": pci.security_score,
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

        # All four headers PCI-005 scores, not three. These are what separates the sites now that
        # they are served with the headers their vercel.json declares.
        presence = {
            "csp_present": pci.csp_header.get("present", False),
            "hsts_present": pci.hsts_header.get("present", False),
            "referrer_policy_present": pci.referrer_policy.get("present", False),
            "x_frame_options_present": pci.x_frame_options.get("present", False),
            "x_content_type_present": pci.x_content_type.get("present", False),
        }
        for key, actual in presence.items():
            if key in pci_exp:
                total += 1
                passed += int(_check(key, actual == pci_exp[key], actual, pci_exp[key]))

    # Tech stack drives the Razorpay integration recommendation, so a wrong stack means a wrong
    # recommendation even when every compliance number is right.
    if "expected_stack" in gt and state.integration_result:
        detected = list((state.integration_result.detected_stack or {}).keys())
        total += 1
        passed += int(_check("Detected stack", detected == [gt["expected_stack"]],
                             detected, [gt["expected_stack"]]))
        total += 1
        passed += int(_check("Starter code non-empty", bool(state.integration_result.starter_code),
                             len(state.integration_result.starter_code or ""), "> 0 chars"))

    print(f"\n  Result: {passed}/{total} checks passed")
    return passed == total


async def _active_path() -> str:
    """Which scoring path this run actually took.

    Reporting the configured path is not the same thing. An expired token leaves the engine
    silently falling back to rule-based scoring while every setting still says LLM, so a
    transcript would claim the LLM path was exercised when it was not. This probes the endpoint
    and reports what really happened.
    """
    from backend.config import get_settings
    from backend.tools.llm_client import llm_complete

    settings = get_settings()
    # The same condition llm_complete uses. Branching on the key alone reported the model path
    # for a run with OPENAI_BASE_URL empty, where llm_complete returns "" without raising and
    # every score silently fell back to rules.
    if settings.openai_api_key and settings.openai_base_url:
        configured = f"OpenAI-compatible endpoint ({settings.llm_model})"
    elif settings.anthropic_api_key:
        configured = f"Anthropic ({settings.anthropic_model})"
    elif settings.openai_api_key:
        return "rule-only, OPENAI_API_KEY is set but OPENAI_BASE_URL is empty, so nothing is called"
    else:
        return "rule-only, no LLM credentials configured"

    try:
        answer = await llm_complete("Reply with exactly: PONG")
    except Exception as e:
        return (
            f"rule-only. {configured} is configured but UNREACHABLE "
            f"({type(e).__name__}), so every policy score fell back to rules"
        )

    # An empty completion is the fallback path wearing the configured path's name.
    if not answer.strip():
        return (
            f"rule-only. {configured} is configured and returned an empty completion, "
            "so every policy score fell back to rules"
        )
    return f"LLM-refined via {configured}, reachable"


async def main() -> bool:
    path = await _active_path()
    print(f"Scoring path: {path}")

    # The recorded exact scores are rule-path values, so they are only asserted on that path.
    rule_path = path.startswith("rule-only")

    results = []
    for name, gt_file in TEST_CASES:
        ok = await validate_one(name, gt_file, rule_path=rule_path)
        results.append((name, ok))

    print(f"\n{'='*60}")
    print("GROUND TRUTH VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Scoring path: {path}")
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
    total_passed = sum(1 for _, ok in results if ok)
    print(f"\n{total_passed}/{len(results)} test sites passed")
    return total_passed == len(results)


if __name__ == "__main__":
    # Without this the summary could read 0/4 and still exit 0, so nothing could gate on it.
    sys.exit(0 if asyncio.run(main()) else 1)
