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


class TestASiteThatRedirectsToAnotherDomainIsStillCrawled:
    """A rebrand silently emptied the entire crawl, and the score went up rather than failing.

    wowskinscienceindia.com answers 301 to buywow.in. The crawler pinned the base domain to the
    URL the merchant typed, so after the redirect every link on the page read as off-domain and
    was discarded: zero pages identified, zero policies found by link discovery, and the auditor
    fell back to keyword-matching the homepage and graded the homepage as the refund policy. The
    site scored 52 and a C, which is worse than failing, because a wrong answer in the generous
    direction is the one a merchant will act on.

    Host and port together make the domain here, so two loopback ports reproduce a cross-domain
    redirect exactly.
    """

    @staticmethod
    def _serve_old_domain_redirecting_to_new():
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        refund = (
            b"<!doctype html><html><body><h1>Refund Policy</h1><p>"
            + (b"You may request a refund or cancellation within 30 days. "
               b"Our return policy covers damaged goods. ") * 30
            + b"</p></body></html>"
        )

        class NewHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Absolute hrefs, the way a hosted storefront emits them. A relative href would
                # rejoin against the old base and survive the redirect by accident, which is what
                # made the first version of this test pass against the bug.
                home = (
                    "<!doctype html><html><body><h1>Wow</h1>"
                    f"<a href='http://{self.headers['Host']}/policies/refund-policy'>"
                    "Refund Policy</a></body></html>"
                ).encode()
                path = self.path.split("?")[0].rstrip("/")
                body = {"": home, "/policies/refund-policy": refund}.get(path)
                self.send_response(200 if body else 404)
                self.send_header("Content-Type", "text/html")
                body = body or b"not found"
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        new = ThreadingHTTPServer(("127.0.0.1", 0), NewHandler)
        threading.Thread(target=new.serve_forever, daemon=True).start()
        new_port = new.server_address[1]

        class OldHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(301)
                self.send_header("Location", f"http://127.0.0.1:{new_port}{self.path}")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        old = ThreadingHTTPServer(("127.0.0.1", 0), OldHandler)
        threading.Thread(target=old.serve_forever, daemon=True).start()
        return old, new, old.server_address[1]

    async def test_links_on_the_new_domain_are_followed(self):
        from backend.tools.crawler_tools import crawl_website

        old, new, old_port = self._serve_old_domain_redirecting_to_new()
        try:
            result = await crawl_website(f"http://127.0.0.1:{old_port}", max_pages=10, timeout=20)
        finally:
            for s in (old, new):
                s.shutdown()
                s.server_close()

        assert "refund" in result["identified_pages"], (
            "after a redirect to another domain every link was discarded as off-domain, so the "
            f"crawl found nothing: {result['identified_pages']}"
        )
        html = result["pages_found"].get(result["identified_pages"]["refund"], "")
        assert "Refund Policy" in html, "the policy was identified but never fetched"


class TestARedirectCannotSmuggleTheCrawlerInternally:
    """Adopting the landed domain must not become an SSRF bypass.

    The scan target is checked before the crawl, but a public site answering 302 to
    169.254.169.254 would otherwise have its metadata read and returned inside the report.
    """

    def test_the_landed_url_is_re_checked(self):
        from backend.tools.crawler_tools import url_refusal_reason

        assert url_refusal_reason("http://169.254.169.254/latest/meta-data/", allow_loopback=True)

    async def test_a_redirect_to_an_internal_host_is_refused_not_merely_unreachable(self):
        """The refusal has to be the thing that stops it.

        An earlier version of this test asserted only that no page came back, and it passed
        against unguarded code because the metadata address is simply unroutable from a test
        machine. A timeout is not a control. So this asserts the recorded reason names the
        refusal, which is false unless the guard actually fired.
        """
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from backend.tools.crawler_tools import crawl_website

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = await crawl_website(
                f"http://127.0.0.1:{server.server_address[1]}", max_pages=5, timeout=15
            )
        finally:
            server.shutdown()
            server.server_close()

        assert result["pages_found"] == {}, (
            "a redirect to a link-local metadata endpoint was crawled and its content kept"
        )
        assert any("not a public address" in e for e in result["crawl_errors"]), (
            f"the crawl stopped, but not because the address was refused: {result['crawl_errors']}"
        )


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
    def _serve_store_with_a_return_gifts_category():
        """A real pattern: a catalogue link whose text reads like a policy.

        Chumbak sells "Return Gifts", party favours, at /collections/return-gifts. The link text
        classifies as a refund policy, so that shopping category was registered as the refund page
        and graded, while the actual policy sat unlinked at /policies/refund-policy.
        """
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        home = (
            b"<!doctype html><html><body><h1>Shop</h1>"
            b"<a href='/collections/return-gifts'>Return Gifts</a>"
            b"</body></html>"
        )
        category = (
            b"<!doctype html><html><body><h1>Return Gifts</h1>"
            b"<p>Party favours and thank you gifts for your guests.</p></body></html>"
        )
        policy = (
            b"<!doctype html><html><body><h1>Refund Policy</h1><p>"
            + (b"You may request a refund or cancellation within 30 days. "
               b"Our return policy covers damaged goods. ") * 30
            + b"</p></body></html>"
        )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?")[0].rstrip("/")
                body = {
                    "": home,
                    "/collections/return-gifts": category,
                    "/policies/refund-policy": policy,
                }.get(path)
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

    async def test_a_declared_url_beats_a_link_whose_text_merely_reads_like_one(self):
        """Link text is the weaker evidence, so it must not block the search for the real page."""
        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_store_with_a_return_gifts_category()
        try:
            result = await crawl_website(f"http://127.0.0.1:{port}", max_pages=10, timeout=20)
        finally:
            server.shutdown()
            server.server_close()

        refund_url = result["identified_pages"].get("refund", "")
        assert refund_url.endswith("/policies/refund-policy"), (
            f"a shopping category was graded as the refund policy: {refund_url}"
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


class TestASessionAwareSiteIsNotGradedOnItsShell:
    """A storefront served the real page once and a skeleton to every later request in the session.

    Measured on a live Shopify store: with one browser context shared across the crawl the
    homepage came back at 1.6MB and every policy page after it at 10KB and 26 words. With a fresh
    context per page every one came back in full. The engine was grading a loading skeleton and
    reporting the merchant's perfectly good shipping policy as quality 1, which is a false
    negative in the direction that costs a real merchant real money.

    Neither a longer settle nor a browser user agent changed it, so this is about the session, not
    about rendering time or being taken for a bot.
    """

    @staticmethod
    def _serve_site_that_shells_a_returning_session():
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        policy = (
            b"<!doctype html><html><body><h1>Shipping Policy</h1><p>"
            + (b"Orders are dispatched within two days by courier. Delivery time is five to "
               b"seven days. Shipping charges are shown at checkout. ") * 30
            + b"</p></body></html>"
        )
        home = (
            b"<!doctype html><html><body><h1>Shop</h1>"
            b"<a href='/shipping-policy'>Shipping Policy</a></body></html>"
        )
        shell = b"<!doctype html><html><body><div id='app'></div></body></html>"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                returning = "seen=1" in (self.headers.get("Cookie") or "")
                path = self.path.split("?")[0].rstrip("/")
                if returning:
                    body = shell
                else:
                    body = {"": home, "/shipping-policy": policy}.get(path, b"not found")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Set-Cookie", "seen=1; Path=/")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, server.server_address[1]

    async def test_the_policy_page_is_read_not_the_skeleton(self):
        from backend.tools.crawler_tools import crawl_website

        server, port = self._serve_site_that_shells_a_returning_session()
        try:
            result = await crawl_website(f"http://127.0.0.1:{port}", max_pages=5, timeout=20)
        finally:
            server.shutdown()
            server.server_close()

        url = result["identified_pages"].get("shipping", "")
        assert url, f"the shipping policy was never identified: {result['identified_pages']}"
        html = result["pages_found"].get(url, "")
        assert "dispatched within two days" in html, (
            f"the crawl kept a {len(html)} byte skeleton instead of the policy page"
        )


class TestPolicyPagesListedInTheSitemapAreFound:
    """A site's own sitemap is the one authoritative list of its URLs, and nothing read it.

    Link discovery sees what the homepage exposes, and probing guesses a handful of conventional
    paths. Neither finds a policy at `/info/shipping-policy`: it is not linked, and `/info` is not
    a prefix worth guessing. The sitemap names it outright.

    Measured caveat, recorded because it decides how much this is worth: one real storefront's
    sitemap listed products, collections and blog posts and no policy pages at all, because legal
    pages carry no SEO value. So this is an extra source of truth, not a replacement for the other
    two.
    """

    POLICY = (
        "<!doctype html><html><body><h1>Shipping Policy</h1><p>"
        + ("Orders are dispatched within two days by courier. Delivery time is five to "
           "seven days. Shipping charges are shown at checkout. " * 30)
        + "</p></body></html>"
    )
    HOME = "<!doctype html><html><body><h1>Shop</h1><a href='/about'>About</a></body></html>"

    @classmethod
    def _serve(cls, *, robots_sitemap=None, at_default_sitemap=True, nested=False, products=0):
        """A store whose shipping policy is reachable only through its sitemap.

        robots_sitemap: path to advertise in robots.txt, or None for no robots.txt
        at_default_sitemap: also serve /sitemap.xml
        nested: /sitemap.xml is a sitemapindex pointing at the real urlset
        products: how many product URLs to bury the policy among
        """
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        holder = {}

        def urlset(host):
            locs = [f"http://{host}/products/item-{i}" for i in range(products)]
            locs.append(f"http://{host}/info/shipping-policy")
            body = "".join(f"<url><loc>{u}</loc></url>" for u in locs)
            return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'

        def index(host):
            return (
                '<?xml version="1.0"?><sitemapindex '
                'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"<sitemap><loc>http://{host}/sm/pages.xml</loc></sitemap></sitemapindex>"
            )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                host = self.headers["Host"]
                path = self.path.split("?")[0].rstrip("/")
                body = None
                if path == "":
                    body = cls.HOME
                elif path == "/info/shipping-policy":
                    body = cls.POLICY
                elif path == "/robots.txt":
                    if robots_sitemap:
                        body = f"User-agent: *\nAllow: /\nSitemap: http://{host}{robots_sitemap}\n"
                elif path == "/sitemap.xml" and at_default_sitemap:
                    body = index(host) if nested else urlset(host)
                elif path in ("/sm/pages.xml", robots_sitemap):
                    body = urlset(host)
                elif path.startswith("/products/"):
                    body = "<html><body><h1>A product</h1></body></html>"

                encoded = (body or "not found").encode()
                self.send_response(200 if body else 404)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        holder["server"] = server
        return server, server.server_address[1]

    async def _crawl(self, server, port, **kw):
        from backend.tools.crawler_tools import crawl_website

        try:
            return await crawl_website(f"http://127.0.0.1:{port}", timeout=20, **kw)
        finally:
            server.shutdown()
            server.server_close()

    async def test_a_policy_url_only_in_the_sitemap_is_found(self):
        server, port = self._serve()
        result = await self._crawl(server, port, max_pages=10)

        url = result["identified_pages"].get("shipping", "")
        assert url.endswith("/info/shipping-policy"), (
            f"the sitemap named the shipping policy and it was not found: "
            f"{result['identified_pages']}"
        )
        assert "dispatched within two days" in result["pages_found"].get(url, ""), (
            "the policy was identified from the sitemap but never fetched"
        )

    async def test_the_sitemap_named_in_robots_txt_is_used(self):
        """The sitemap is not always at /sitemap.xml, and robots.txt is where a site says so."""
        server, port = self._serve(robots_sitemap="/sm/pages.xml", at_default_sitemap=False)
        result = await self._crawl(server, port, max_pages=10)

        assert result["identified_pages"].get("shipping", "").endswith("/info/shipping-policy"), (
            f"robots.txt named the sitemap and it was not read: {result['identified_pages']}"
        )

    async def test_a_nested_sitemap_index_is_followed(self):
        """Large sites publish a sitemapindex of sitemaps, which is what a real store served."""
        server, port = self._serve(nested=True)
        result = await self._crawl(server, port, max_pages=10)

        assert result["identified_pages"].get("shipping", "").endswith("/info/shipping-policy"), (
            f"a nested sitemap index was not followed: {result['identified_pages']}"
        )

    async def test_a_large_product_sitemap_neither_misleads_nor_blows_the_budget(self):
        """A real sitemap is mostly products. None of them is a policy, and none is worth fetching."""
        server, port = self._serve(products=600)
        result = await self._crawl(server, port, max_pages=8)

        assert result["identified_pages"].get("shipping", "").endswith("/info/shipping-policy")
        assert not any(
            "/products/" in u for u in result["identified_pages"].values()
        ), f"a product page was registered as a policy: {result['identified_pages']}"
        assert result["pages_crawled"] <= 8, (
            f"the sitemap pushed the crawl past its page budget: {result['pages_crawled']}"
        )
