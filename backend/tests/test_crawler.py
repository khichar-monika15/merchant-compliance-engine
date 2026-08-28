import pytest

from backend.tools.crawler_tools import (
    POLICY_LINK_TEXT_PATTERNS,
    POLICY_URL_PATTERNS,
    _classify_link_text,
    _classify_url_as_policy,
    _detect_tech_stack,
)


class TestPolicyURLClassification:
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com/refund-policy", "refund"),
        ("https://example.com/privacy-policy", "privacy"),
        ("https://example.com/terms-and-conditions", "terms"),
        ("https://example.com/contact-us", "contact"),
        ("https://example.com/checkout", "checkout"),
        ("https://example.com/about", None),
        ("https://example.com/products", None),
    ])
    def test_url_classification(self, url, expected):
        result = _classify_url_as_policy(url)
        assert result == expected


class TestPolicyLinkTextClassification:
    @pytest.mark.parametrize("text,expected", [
        ("Refund Policy", "refund"),
        ("Privacy Policy", "privacy"),
        ("Terms of Service", "terms"),
        ("Contact Us", "contact"),
        ("About Us", None),
        ("Home", None),
    ])
    def test_link_text_classification(self, text, expected):
        result = _classify_link_text(text)
        assert result == expected


class TestTechStackDetection:
    def test_shopify_detected(self):
        html = '<script src="https://cdn.shopify.com/theme.js"></script><div class="shopify-section"></div>'
        result = _detect_tech_stack(html, {}, [])
        assert "shopify" in result

    def test_wordpress_detected(self):
        html = '<link rel="stylesheet" href="/wp-content/themes/style.css">'
        result = _detect_tech_stack(html, {}, [])
        assert "wordpress" in result

    def test_nextjs_detected(self):
        html = '<script src="/_next/static/chunks/main.js"></script><script>window.__NEXT_DATA__={}</script>'
        result = _detect_tech_stack(html, {}, [])
        assert "nextjs" in result

    def test_react_detected(self):
        html = '<div data-reactroot=""></div><script src="/static/js/react-dom.js"></script>'
        result = _detect_tech_stack(html, {}, [])
        assert "react" in result

    def test_django_detected(self):
        html = '<input type="hidden" name="csrfmiddlewaretoken" value="abc123">'
        result = _detect_tech_stack(html, {}, [])
        assert "django" in result

    def test_static_html_fallback(self):
        html = "<html><body><h1>Hello World</h1></body></html>"
        result = _detect_tech_stack(html, {}, [])
        assert "static_html" in result
