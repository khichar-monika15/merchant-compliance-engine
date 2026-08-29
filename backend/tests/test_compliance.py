import pytest

from backend import knowledge

from backend.agents.compliance_auditor import (
    _check_contact_page,
    _check_gst_display,
    _detect_business_category,
    _html_to_text,
    _llm_quality_score,
    _overall_score,
    _search_page_for_policy,
)
from backend.models.schemas import ComplianceCheck, Severity


def _check(found: bool, quality: int) -> ComplianceCheck:
    return ComplianceCheck(
        check_id="RBI-001", name="x", found=found, quality_score=quality,
        severity=Severity.CRITICAL, issues=[],
    )


class TestOverallScore:
    """RBI score must track policy quality, not just presence.

    It used to be `(passed / 4) * 80` where passed was a binary gate at quality >= 5, so a
    thin policy scraping a 5 and a thorough one scoring 10 earned identical credit — and the
    LLM's refinement only mattered if it happened to cross that single threshold.
    """

    def test_thorough_policies_outscore_barely_adequate_ones(self):
        thorough = [_check(True, 10)] * 4
        barely = [_check(True, 5)] * 4
        assert _overall_score(thorough, gst_found=True) > _overall_score(barely, gst_found=True)

    def test_perfect_site_scores_100(self):
        assert _overall_score([_check(True, 10)] * 4, gst_found=True) == 100

    def test_missing_policies_score_zero_regardless_of_quality_field(self):
        assert _overall_score([_check(False, 9)] * 4, gst_found=False) == 0

    def test_gst_display_is_worth_20(self):
        checks = [_check(False, 0)] * 4
        assert _overall_score(checks, gst_found=True) - _overall_score(checks, gst_found=False) == 20


class TestContactRedFlags:
    """RBI-004 lists red flags for a contact page; nothing read them until now.

    RBI's Merchant Due Diligence expects an Indian place of business, so a merchant showing a
    New York address or a placeholder email is a real onboarding signal, not a pass.
    """

    def test_foreign_address_is_flagged(self):
        html = """
        <p>Address: 350 Fifth Avenue, New York, NY 10118</p>
        <p>Phone: +91 9876543210</p>
        <p>Email: help@quickbites.in</p>
        """
        _, issues = _check_contact_page(html)
        assert any("india" in i.lower() or "outside" in i.lower() for i in issues), issues

    def test_placeholder_email_is_flagged(self):
        html = "<p>Email: test@test.com</p><p>1/4 MG Road, Bangalore 560001</p><p>+91 9876543210</p>"
        _, issues = _check_contact_page(html)
        assert any("placeholder" in i.lower() for i in issues), issues

    def test_genuine_indian_contact_page_has_no_red_flag(self):
        html = """
        <p>Address: 1/4 MG Road, Bangalore 560001, Karnataka</p>
        <p>Phone: +91 9876543210</p>
        <p>Email: support@artisanweaves.in</p>
        """
        _, issues = _check_contact_page(html)
        assert issues == []


class TestContactPageChecker:
    def test_complete_contact_info(self):
        html = """
        <p>Address: 123 MG Road, Bangalore 560001, Karnataka, India</p>
        <p>Phone: +91 9876543210</p>
        <p>Email: support@artisanweaves.in</p>
        """
        found, issues = _check_contact_page(html)
        assert found is True
        assert len(issues) == 0

    def test_email_only_contact(self):
        html = "<p>Email: hello@freshkart.in</p>"
        found, issues = _check_contact_page(html)
        assert found is True  # email present = found
        assert any("phone" in issue.lower() for issue in issues)
        assert any("address" in issue.lower() for issue in issues)

    def test_no_contact_at_all(self):
        html = "<p>We will get in touch with you soon.</p>"
        found, issues = _check_contact_page(html)
        assert found is False
        assert len(issues) > 0

    def test_script_body_does_not_satisfy_phone_or_address(self):
        """Digits inside a script and 'road' inside 'broadcast' used to pass both checks."""
        html = """
        <p>Email: hi@shop.in</p>
        <script>var t = 9876543210123; var mode = "broadcast";</script>
        """
        found, issues = _check_contact_page(html)
        assert found is True  # email is real
        assert any("phone" in i.lower() for i in issues)
        assert any("address" in i.lower() for i in issues)

    def test_country_name_alone_is_not_an_address(self):
        html = "<footer><p>Made in India</p><p>Email: hi@shop.in</p></footer>"
        _, issues = _check_contact_page(html)
        assert any("address" in i.lower() for i in issues)

    @pytest.mark.parametrize("phone", [
        "+91 98765 43210",      # mobile, spaced
        "+91-522-4001-234",     # STD landline
        "09876543210",          # trunk-prefixed mobile
        "9876543210",           # bare mobile
    ])
    def test_accepts_mobile_and_landline_formats(self, phone):
        found, issues = _check_contact_page(f"<p>Email: hi@shop.in</p><p>Phone: {phone}</p>")
        assert found is True
        assert not any("phone" in i.lower() for i in issues), f"{phone} rejected"

    def test_real_indian_address_with_pin_accepted(self):
        html = """
        <p>Email: hi@shop.in</p>
        <p>Phone: +91 98765 43210</p>
        <p>14 Hazratganj, Lucknow 226001, Uttar Pradesh, India</p>
        """
        found, issues = _check_contact_page(html)
        assert found is True
        assert issues == []


class TestGSTDisplay:
    def test_valid_gstin_detected(self):
        html = "Our GSTIN: 29ABCDE1234F1Z5"
        found, number = _check_gst_display(html)
        assert found is True
        assert number == "29ABCDE1234F1Z5"

    def test_no_gst_number(self):
        html = "<p>Welcome to our store</p>"
        found, number = _check_gst_display(html)
        assert found is False
        assert number is None

    def test_gst_in_footer(self):
        html = """
        <footer>
          <p>GST No: 27AAPFU0939F1ZV</p>
        </footer>
        """
        found, number = _check_gst_display(html)
        assert found is True

    def test_commented_out_gstin_does_not_count(self):
        """A GSTIN must be shown to customers — markup in a comment is not displayed."""
        html = "<p>About us</p><!-- No GSTIN: 27AAPFU0939F1ZV -->"
        found, number = _check_gst_display(html)
        assert found is False
        assert number is None

    def test_placeholder_gstin_rejected(self):
        found, number = _check_gst_display("<p>GSTIN: 27XXXXX1234X1ZX</p>")
        assert found is False

    def test_knowledge_base_red_flag_gstin_rejected(self):
        found, number = _check_gst_display("<p>GSTIN: 00AAAAA0000A0Z0</p>")
        assert found is False

    def test_real_gstin_wins_over_placeholder(self):
        html = "<p>GSTIN: 27XXXXX1234X1ZX</p><footer>GSTIN: 29ABCDE1234F1Z5</footer>"
        found, number = _check_gst_display(html)
        assert found is True
        assert number == "29ABCDE1234F1Z5"


class TestBusinessCategoryDetection:
    def test_ecommerce_detected(self):
        html = "<button>Add to Cart</button><a href='/checkout'>Buy Now</a>"
        result = _detect_business_category(html)
        assert result == "ecommerce"

    def test_saas_detected(self):
        html = "<p>Start free trial</p><p>$9 per month</p><a href='/pricing'>Pricing Plans</a>"
        result = _detect_business_category(html)
        assert result == "saas"

    def test_food_delivery_detected(self):
        html = "<h1>Order food online</h1><p>Browse our restaurant menu</p>"
        result = _detect_business_category(html)
        assert result == "food_delivery"


class TestHtmlToText:
    def test_strips_html_tags(self):
        html = "<h1>Hello <strong>World</strong></h1>"
        result = _html_to_text(html)
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result

    def test_decodes_entities(self):
        html = "<p>Terms &amp; Conditions apply</p>"
        result = _html_to_text(html)
        assert "&amp;" not in result
        assert "Terms and Conditions" in result

    def test_ampersand_normalised_to_and(self):
        html = "<h1>Terms &amp; Conditions</h1>"
        result = _html_to_text(html)
        assert "terms and conditions" in result.lower()


# These used to be hand-written copies of RBI-003 and RBI-001, so changing min_word_count or
# body_keywords in the checklist could not fail these tests. They read the real checks now.
_TERMS_CHECK = knowledge.rbi_check("RBI-003")
_REFUND_CHECK = knowledge.rbi_check("RBI-001")


class TestSearchPageForPolicy:
    def test_plain_text_match(self):
        html = "<p>Governing law of India. User agreement terms and conditions apply.</p>"
        found, score = _search_page_for_policy(html, _TERMS_CHECK)
        assert found is True
        assert score > 0

    def test_html_entity_match(self):
        # "Terms &amp; Conditions" should match "terms and conditions" after entity decode
        html = """
        <h1>Terms &amp; Conditions</h1>
        <p>These terms and conditions govern your use. Governing law of India.</p>
        <p>Dispute resolution: contact us first before legal action.</p>
        """
        found, score = _search_page_for_policy(html, _TERMS_CHECK)
        assert found is True

    def test_insufficient_keywords_returns_false(self):
        html = "<p>Welcome to our shop. We sell handloom goods.</p>"
        found, score = _search_page_for_policy(html, _TERMS_CHECK)
        assert found is False
        assert score == 0

    def test_red_flag_caps_score(self):
        html = "<p>Refund policy. Return eligible. Cancellation. Lorem ipsum filler.</p>"
        found, score = _search_page_for_policy(html, _REFUND_CHECK)
        assert found is True
        assert score == 2  # red flag detected

    def test_refund_policy_detected(self):
        html = """
        <h2>Refund Policy</h2>
        <p>We offer full refunds for eligible returns within 7 days of purchase.
        Cancellation requests must be made within 24 hours. Processing time is 5 business days.</p>
        """
        found, score = _search_page_for_policy(html, _REFUND_CHECK)
        assert found is True
        assert score >= 3


class TestLLMQualityScore:
    """Without an LLM the rule-based score must survive — it must not be replaced by a pass."""

    async def test_falls_back_to_rule_based_score(self, monkeypatch):
        monkeypatch.setattr("backend.agents.compliance_auditor.llm_complete", _empty_llm)
        score, details = await _llm_quality_score("Lorem ipsum filler.", "Refund Policy", "ecommerce", topics=["timeline", "eligibility"], fallback=2)
        assert score == 2
        assert "unavailable" in details.lower()

    async def test_llm_score_wins_when_available(self, monkeypatch):
        monkeypatch.setattr("backend.agents.compliance_auditor.llm_complete", _scoring_llm)
        score, details = await _llm_quality_score("A thorough refund policy.", "Refund Policy", "ecommerce", topics=["timeline", "eligibility"], fallback=2)
        assert score == 9
        assert details == "comprehensive"

    async def test_bare_code_fence_is_stripped(self, monkeypatch):
        monkeypatch.setattr("backend.agents.compliance_auditor.llm_complete", _bare_fence_llm)
        score, _ = await _llm_quality_score("Some policy text.", "Refund Policy", "ecommerce", topics=["timeline", "eligibility"], fallback=2)
        assert score == 7


async def _empty_llm(prompt: str, max_tokens: int = 512) -> str:
    return ""


async def _scoring_llm(prompt: str, max_tokens: int = 512) -> str:
    return '{"score": 9, "issues": [], "details": "comprehensive"}'


async def _bare_fence_llm(prompt: str, max_tokens: int = 512) -> str:
    return '```\n{"score": 7, "issues": [], "details": "adequate"}\n```'
