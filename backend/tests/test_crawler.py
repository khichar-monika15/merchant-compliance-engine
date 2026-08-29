import pytest

from backend.tools.crawler_tools import (
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


class TestPolicyURLClassificationWithExtensions:
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com/terms.html", "terms"),
        ("https://example.com/privacy.html", "privacy"),
        ("https://example.com/refund.html", "refund"),
        ("https://example.com/contact.html", "contact"),
        ("https://example.com/terms.php", "terms"),
        ("https://example.com/about.html", None),
    ])
    def test_html_extension_stripped(self, url, expected):
        assert _classify_url_as_policy(url) == expected


class TestTheFrontierDropsSelfReferences:
    """An in-page anchor is not a page.

    `urljoin` turns href="#refund" into "https://site/#refund", whose domain matches and which is
    not yet in pages_found, so it entered the frontier AND was registered by its link text as the
    canonical refund page. The crawler then re-fetched the homepage under that key and graded the
    homepage HTML as the refund policy. On a one-page site with a dozen footer anchors the whole
    page budget went on re-fetching the same document.
    """

    def test_a_fragment_of_a_known_page_is_not_a_new_page(self):
        from backend.tools.crawler_tools import _is_new_page

        seen = {"https://site.example/": "<html></html>"}
        assert not _is_new_page("https://site.example/#refund", seen)
        assert not _is_new_page("https://site.example/", seen)

    def test_a_real_page_is_still_new(self):
        from backend.tools.crawler_tools import _is_new_page

        seen = {"https://site.example/": "<html></html>"}
        assert _is_new_page("https://site.example/refund.html", seen)

    def test_a_query_string_variant_of_a_seen_page_is_not_new(self):
        """?utm_source=x is the same document, and the crawl budget is small."""
        from backend.tools.crawler_tools import _is_new_page

        seen = {"https://site.example/refund.html": "<html></html>"}
        assert not _is_new_page("https://site.example/refund.html?utm_source=footer", seen)


class TestTheScannedUrlIsChecked:
    """A scan target is attacker-controlled input, and the crawler is a browser we drive.

    Nothing checked the URL, so a deployed instance would fetch cloud metadata endpoints or any
    host on its own network on request and return the contents inside the report.
    """

    # Refused whatever the loopback setting is.
    ALWAYS_BLOCKED = [
        "http://169.254.169.254/latest/meta-data/",   # AWS/GCP metadata
        "http://metadata.google.internal/",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/",
        "http://172.16.4.4/",
        "file:///etc/passwd",
        "gopher://internal/",
    ]

    # Reachable locally so the demo works, refused on a deployment.
    LOOPBACK = ["http://127.0.0.1:4001/", "http://[::1]:8000/"]

    @pytest.mark.parametrize("url", ALWAYS_BLOCKED)
    def test_internal_and_non_http_targets_are_refused(self, url):
        from backend.tools.crawler_tools import url_refusal_reason

        assert url_refusal_reason(url, allow_loopback=True), f"{url} was accepted as a scan target"
        assert url_refusal_reason(url, allow_loopback=False), url

    @pytest.mark.parametrize("url", LOOPBACK)
    def test_loopback_is_refused_with_the_deployment_setting(self, url):
        from backend.tools.crawler_tools import url_refusal_reason

        assert url_refusal_reason(url, allow_loopback=False), f"{url} was accepted"

    @pytest.mark.parametrize("url", [
        "https://example.com/",
        "https://shop.example.co.in/checkout",
        "http://merchant.example.org",
    ])
    def test_ordinary_public_sites_are_allowed(self, url):
        from backend.tools.crawler_tools import url_refusal_reason

        assert url_refusal_reason(url) is None, url_refusal_reason(url)

    def test_loopback_is_allowed_only_when_explicitly_enabled(self):
        """The four test sites are served on 127.0.0.1, so the demo needs a deliberate opt-in."""
        from backend.tools.crawler_tools import url_refusal_reason

        assert url_refusal_reason("http://127.0.0.1:4001/", allow_loopback=True) is None
        assert url_refusal_reason("http://127.0.0.1:4001/", allow_loopback=False)
