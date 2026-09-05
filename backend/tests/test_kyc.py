import pytest

from backend.tools.name_matcher import (
    _MISMATCH_DETECTORS,
    _NORMALIZATION_RULES,
    _SIMILARITY_THRESHOLD,
    check_name_pair,
    normalize_name,
    validate_kyc_consistency,
)


class TestGroundedInKnowledgeBase:
    """RBI-006 defines the normalization rules and the similarity threshold.

    The project convention is that compliance checks ground in `backend/knowledge/*.json`. This
    module hardcoded its own copy, so the checklist and the code could drift apart silently.
    """

    def test_rules_come_from_the_checklist(self):
        import json
        from pathlib import Path

        db = json.loads((Path("backend/knowledge/rbi_mdd_checklist.json")).read_text())
        rbi_006 = next(c for c in db["checks"] if c["id"] == "RBI-006")
        criteria = rbi_006["quality_criteria"]

        assert _SIMILARITY_THRESHOLD == criteria["min_similarity_threshold"]
        assert len(_NORMALIZATION_RULES) == len(criteria["normalization_rules"])

    def test_every_declared_mismatch_pattern_has_a_detector(self):
        import json
        from pathlib import Path

        db = json.loads((Path("backend/knowledge/rbi_mdd_checklist.json")).read_text())
        rbi_006 = next(c for c in db["checks"] if c["id"] == "RBI-006")
        declared = set(rbi_006["quality_criteria"]["known_mismatch_patterns"])

        assert declared <= set(_MISMATCH_DETECTORS), (
            f"declared in the checklist but never detected: {declared - set(_MISMATCH_DETECTORS)}"
        )

    def test_co_vs_company_is_detected(self):
        result = check_name_pair("Sharma Co", "Sharma Company", "PAN", "GST")
        assert result["match"] is False
        assert any("Co vs Company" in i for i in result["issues"]), result["issues"]

    def test_intl_vs_international_is_detected(self):
        result = check_name_pair("Verma Intl Traders", "Verma International Traders", "PAN", "GST")
        assert result["match"] is False
        assert any("Intl vs International" in i for i in result["issues"]), result["issues"]

    def test_abbreviation_match_is_word_bounded(self):
        """'co' sits inside 'Cotton' and 'Company'; only a whole word counts."""
        result = check_name_pair("Cotton Company Ltd", "Cotton Company Limited", "PAN", "GST")
        assert not any("Co vs Company" in i for i in result["issues"]), result["issues"]


class TestNormalizeName:
    def test_pvt_to_private(self):
        assert "private" in normalize_name("ABC Pvt. Ltd.")

    def test_ltd_to_limited(self):
        assert "limited" in normalize_name("XYZ Ltd.")

    def test_ampersand_to_and(self):
        assert "and" in normalize_name("A & B Corp")

    def test_strips_dots_commas(self):
        result = normalize_name("A.B.C., Ltd.")
        assert "." not in result
        assert "," not in result

    def test_lowercase(self):
        result = normalize_name("FRESHKART PRIVATE LIMITED")
        assert result == result.lower()


class TestCheckNamePair:
    def test_identical_names_match(self):
        result = check_name_pair("ABC Private Limited", "ABC PRIVATE LIMITED", "PAN", "GST")
        assert result["match"] is True
        assert result["similarity"] > 0.95

    def test_pvt_private_mismatch_detected(self):
        result = check_name_pair("ABC Pvt. Ltd.", "ABC PRIVATE LIMITED", "PAN", "GST")
        assert result["match"] is False
        assert any("Pvt" in issue for issue in result["issues"])

    def test_completely_different_names(self):
        result = check_name_pair("XYZ Corp", "ABC Limited", "PAN", "GST")
        assert result["match"] is False
        assert result["similarity"] < 0.5

    def test_spacing_difference(self):
        result = check_name_pair("FreshKart Private Limited", "Fresh Kart Private Limited", "GST", "Bank")
        issues_text = " ".join(result["issues"])
        assert "spacing" in issues_text.lower(), result["issues"]

    def test_spacing_is_reported_when_the_wording_also_differs(self):
        """The abbreviation must not hide the spacing.

        'FreshKart Pvt. Ltd.' against 'Fresh Kart Private Limited' differs two ways, and only one
        of them is something the merchant can act on. Run on the raw names the spacing is
        invisible, because 'freshkartpvt.ltd.' and 'freshkartprivatelimited' differ anyway.
        """
        result = check_name_pair("FreshKart Pvt. Ltd.", "Fresh Kart Private Limited", "PAN", "Bank")
        issues_text = " ".join(result["issues"]).lower()
        assert "spacing" in issues_text, result["issues"]

    @pytest.mark.parametrize("name", ["Anand & Sons", "Brands & Co", "Chandra & Standard Traders"])
    def test_identical_name_with_ampersand_matches(self, name):
        """A name containing both '&' and the letters 'and' must not mismatch against itself."""
        result = check_name_pair(name, name, "PAN", "GST")
        assert result["match"] is True
        assert result["issues"] == []

    def test_ampersand_vs_spelled_out_still_detected(self):
        result = check_name_pair("ABC & Sons", "ABC and Sons", "PAN", "GST")
        assert result["match"] is False
        assert any("& vs and" in issue for issue in result["issues"])


class TestValidateKYCConsistency:
    def test_all_matching(self):
        result = validate_kyc_consistency(
            "Artisan Weaves Private Limited",
            "ARTISAN WEAVES PRIVATE LIMITED",
            "Artisan Weaves Private Limited",
        )
        assert result["overall_consistent"] is True
        assert result["confidence"] > 0.9

    def test_pvt_vs_private_inconsistency(self):
        result = validate_kyc_consistency(
            "FreshKart Pvt. Ltd.",
            "FRESHKART PRIVATE LIMITED",
            "Fresh Kart Private Limited",
        )
        assert result["overall_consistent"] is False
        assert len(result["common_mismatches"]) > 0

    def test_completely_mismatched(self):
        result = validate_kyc_consistency("ABC Corp", "XYZ Limited", "PQR Inc")
        assert result["overall_consistent"] is False
        assert result["confidence"] < 0.5

    def test_confidence_range(self):
        result = validate_kyc_consistency("Test Pvt Ltd", "TEST PRIVATE LIMITED", "Test Private Limited")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_identical_ampersand_names_are_consistent(self):
        result = validate_kyc_consistency("Anand & Sons", "Anand & Sons", "Anand & Sons")
        assert result["overall_consistent"] is True
        assert result["common_mismatches"] == []
