from backend.agents.compliance_auditor import (
    _check_contact_page,
    _check_gst_display,
    _detect_business_category,
    _html_to_text,
    _llm_quality_score,
    _search_page_for_policy,
)


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


_TERMS_CHECK = {
    "search": {
        "body_keywords": [
            "terms of service",
            "terms and conditions",
            "user agreement",
            "governing law",
            "dispute resolution",
        ]
    },
    "quality_criteria": {"min_word_count": 300, "red_flags": ["lorem ipsum"]},
}

_REFUND_CHECK = {
    "search": {
        "body_keywords": [
            "refund",
            "return",
            "cancellation",
            "eligible",
            "processing time",
        ]
    },
    "quality_criteria": {"min_word_count": 200, "red_flags": ["lorem ipsum"]},
}


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
        score, details = await _llm_quality_score("Lorem ipsum filler.", "Refund Policy", "ecommerce", fallback=2)
        assert score == 2
        assert "unavailable" in details.lower()

    async def test_llm_score_wins_when_available(self, monkeypatch):
        monkeypatch.setattr("backend.agents.compliance_auditor.llm_complete", _scoring_llm)
        score, details = await _llm_quality_score("A thorough refund policy.", "Refund Policy", "ecommerce", fallback=2)
        assert score == 9
        assert details == "comprehensive"

    async def test_bare_code_fence_is_stripped(self, monkeypatch):
        monkeypatch.setattr("backend.agents.compliance_auditor.llm_complete", _bare_fence_llm)
        score, _ = await _llm_quality_score("Some policy text.", "Refund Policy", "ecommerce", fallback=2)
        assert score == 7


async def _empty_llm(prompt: str, max_tokens: int = 512) -> str:
    return ""


async def _scoring_llm(prompt: str, max_tokens: int = 512) -> str:
    return '{"score": 9, "issues": [], "details": "comprehensive"}'


async def _bare_fence_llm(prompt: str, max_tokens: int = 512) -> str:
    return '```\n{"score": 7, "issues": [], "details": "adequate"}\n```'
