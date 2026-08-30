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


class TestASiteThatNeverGoesIdleIsStillCrawled:
    """Real merchant sites do not go network idle, and the crawler discarded them entirely.

    `page.goto(wait_until="networkidle")` waits for 500ms of network silence. An e-commerce site
    with analytics beacons, a chat widget and polling never has 500ms of silence, so goto raised
    a timeout and the whole page was thrown away even though its HTML had been ready for seconds.
    Every synthetic test site is static and goes idle instantly, which is exactly why this
    survived: it works in the lab and fails on the open web.
    """

    @staticmethod
    def _serve_a_noisy_page():
        """A page that keeps fetching forever, so networkidle can never fire."""
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        html = (
            b"<!doctype html><html><head><title>Noisy</title></head><body>"
            b"<h1>Refund Policy</h1><p>Our refund policy is described here in detail.</p>"
            b"<a href='/contact.html'>Contact us</a>"
            b"<script>setInterval(function(){fetch('/beacon?t='+Date.now())},100)</script>"
            b"</body></html>"
        )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"ok" if self.path.startswith("/beacon") else html
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, server.server_address[1]

    async def test_the_page_is_returned_despite_constant_network_activity(self):
        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_a_noisy_page()
        try:
            result = await crawl_website(f"http://127.0.0.1:{port}", max_pages=2, timeout=20)
        finally:
            server.shutdown()
            server.server_close()

        assert result["pages_found"], (
            f"a page that never goes network idle was discarded entirely: "
            f"{result.get('crawl_errors')}"
        )
        html = next(iter(result["pages_found"].values()))
        assert "Refund Policy" in html, "the page was fetched but its content was not captured"

    async def test_it_does_not_take_the_whole_timeout(self):
        """The point is to stop waiting for silence, not to wait longer for it."""
        import time

        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_a_noisy_page()
        try:
            start = time.perf_counter()
            await crawl_website(f"http://127.0.0.1:{port}", max_pages=1, timeout=30)
            elapsed = time.perf_counter() - start
        finally:
            server.shutdown()
            server.server_close()

        assert elapsed < 25, f"the crawl still waited {elapsed:.1f}s for a page that loads instantly"


class TestPolicyPagesAreProbedNotOnlyDiscovered:
    """The declared url_patterns find pages, they do not merely label links.

    On a real store the crawler saw only the links the homepage happened to expose, so a refund
    policy sitting at its conventional URL but not linked from the front page was never fetched.
    The auditor then graded whatever other page contained a couple of keywords and reported a
    quality of 1 for a policy that scores 6 when the right page is read. Every synthetic test site
    links all of its policies from the footer, which is why this only appeared off the lab.
    """

    @staticmethod
    def _serve_site_with_unlinked_policy():
        """A homepage linking only to /about, with a real refund policy at its conventional URL."""
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        home = b"<!doctype html><html><body><h1>Shop</h1><a href='/about'>About</a></body></html>"
        about = b"<!doctype html><html><body><h1>About us</h1><p>We sell things.</p></body></html>"
        refund = (
            b"<!doctype html><html><body><h1>Refund Policy</h1><p>"
            + (b"You may request a refund or cancellation within 30 days. "
               b"Our return policy covers damaged goods. ") * 30
            + b"</p></body></html>"
        )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?")[0].rstrip("/")
                body = {"": home, "/about": about, "/refund-policy": refund}.get(path)
                self.send_response(200 if body else 404)
                self.send_header("Content-Type", "text/html")
                body = body or b"not found"
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, server.server_address[1]

    async def test_an_unlinked_policy_at_a_declared_url_is_found(self):
        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_site_with_unlinked_policy()
        try:
            result = await crawl_website(f"http://127.0.0.1:{port}", max_pages=10, timeout=20)
        finally:
            server.shutdown()
            server.server_close()

        assert "refund" in result["identified_pages"], (
            "a refund policy at the conventional URL was never found, because nothing on the "
            f"homepage linked to it. Identified: {result['identified_pages']}"
        )
        html = result["pages_found"].get(result["identified_pages"]["refund"], "")
        assert "Refund Policy" in html, "the page was identified but its content was not fetched"

    async def test_probing_does_not_invent_pages_that_are_missing(self):
        """A 404 must not be recorded as a policy page."""
        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_site_with_unlinked_policy()
        try:
            result = await crawl_website(f"http://127.0.0.1:{port}", max_pages=10, timeout=20)
        finally:
            server.shutdown()
            server.server_close()

        assert "privacy" not in result["identified_pages"], (
            "a privacy policy that does not exist was recorded as found"
        )

    @staticmethod
    def _serve_site_that_redirects_unknown_paths_home():
        """A soft 404: every unknown path answers 302 to the homepage, which is very common."""
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        home = b"<!doctype html><html><body><h1>Shop</h1><p>We sell things.</p></body></html>"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?")[0].rstrip("/") == "":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(home)))
                    self.end_headers()
                    self.wfile.write(home)
                    return
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, server.server_address[1]

    async def test_a_soft_404_that_lands_on_the_homepage_is_not_a_policy_page(self):
        """Otherwise the homepage gets graded as the refund policy, which is the older bug back.

        A 302 to `/` answers 200 after redirects, so the status alone says the page exists. What
        rejects it is that the URL finally landed on no longer reads as a refund policy.
        """
        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_site_that_redirects_unknown_paths_home()
        try:
            result = await crawl_website(f"http://127.0.0.1:{port}", max_pages=10, timeout=20)
        finally:
            server.shutdown()
            server.server_close()

        assert result["identified_pages"] == {}, (
            "a site with no policy pages at all reported some, so the homepage would be graded "
            f"as a policy: {result['identified_pages']}"
        )
