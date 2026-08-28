import pytest

from backend.agents.compliance_auditor import _check_contact_page, _check_gst_display, _detect_business_category


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


class TestBusinessCategoryDetection:
    def test_ecommerce_detected(self):
        html = "<button>Add to Cart</button><a href='/checkout'>Buy Now</a>"
        result = _detect_business_category(html, {})
        assert result == "ecommerce"

    def test_saas_detected(self):
        html = "<p>Start free trial</p><p>$9 per month</p><a href='/pricing'>Pricing Plans</a>"
        result = _detect_business_category(html, {})
        assert result == "saas"

    def test_food_delivery_detected(self):
        html = "<h1>Order food online</h1><p>Browse our restaurant menu</p>"
        result = _detect_business_category(html, {})
        assert result == "food_delivery"
