import pytest

from backend.tools.name_matcher import check_name_pair, normalize_name, validate_kyc_consistency


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
        # Should detect spacing difference
        issues_text = " ".join(result["issues"])
        assert "spacing" in issues_text.lower() or result["match"] is False

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
