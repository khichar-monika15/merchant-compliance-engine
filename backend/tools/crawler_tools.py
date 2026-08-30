from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Browser, async_playwright

from backend import knowledge
from backend.config import get_settings
from backend.tools.script_analyzer import extract_scripts


# How long to let a client-rendered page settle after the DOM is ready, before giving up on
# quiet and reading the content anyway.
_SETTLE_MS = 4000

# Hosted storefronts keep their policies under a fixed prefix rather than at the bare path, and
# those are exactly the sites that do not link every policy from the homepage.
_POLICY_PATH_PREFIXES = ("", "/pages", "/policies")

# A probe is one cheap HTTP GET with no rendering, and they run concurrently, but a merchant site
# should not receive an unbounded burst of requests from a compliance scan.
_MAX_PROBES = 60

_USER_AGENT = (
    "Mozilla/5.0 (compatible; MCIEBot/1.0; "
    "+https://github.com/khichar-monika15/merchant-compliance-engine)"
)


def _policy_url_patterns() -> dict[str, list[str]]:
    """Discovery patterns from the RBI checklist, plus the PCI payment page list.

    These used to be a private copy in this module and had already drifted: the refund list was
    missing `/money-back`, which RBI-001 declares. Checkout is not an RBI check, so its patterns
    come from the PCI document, where requirements 6.4.3 and 11.6.1 need a payment page.
    """
    patterns = dict(knowledge.policy_url_patterns())
    patterns["checkout"] = [f"/{p}" for p in knowledge.payment_page_patterns()]
    return patterns


POLICY_URL_PATTERNS: dict[str, list[str]] = _policy_url_patterns()
POLICY_LINK_TEXT_PATTERNS: dict[str, list[str]] = knowledge.policy_link_text_patterns()

# Detection rules and the Razorpay recommendation for each stack live together in the knowledge
# base, loaded through the one loader rather than opened here.
TECH_STACK_SIGNALS: dict[str, dict] = knowledge.tech_stack_document()["stacks"]


def _get_base_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def url_refusal_reason(url: str, allow_loopback: bool | None = None) -> str | None:
    """Why this URL must not be scanned, or None when it is a fair target.

    The crawler is a real browser pointed at whatever a caller asks for, and nothing checked the
    target. A deployed instance would fetch a cloud metadata endpoint or any host on its own
    network and hand the contents back inside the report.

    Loopback stays reachable because the four demo sites are served there, but only when
    `ALLOW_LOOPBACK_SCANS` says so, which is the default locally and not in a deployment.
    """
    import ipaddress
    import socket

    if allow_loopback is None:
        allow_loopback = get_settings().allow_loopback_scans

    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return f"{parts.scheme or 'that'} is not a scheme this engine fetches, use http or https"

    host = parts.hostname
    if not host:
        return "no host in the URL"

    if host in ("metadata.google.internal", "metadata"):
        return "cloud metadata endpoints are never scanned"

    # A hostname can resolve to a private address, so resolve before deciding.
    try:
        resolved = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        try:
            resolved = {str(ipaddress.ip_address(host))}
        except ValueError:
            return None  # unresolvable public name, the crawl reports its own failure

    for address in resolved:
        ip = ipaddress.ip_address(address)
        if ip.is_loopback:
            if not allow_loopback:
                return "loopback addresses are not scannable on this instance"
            continue
        if ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return f"{host} resolves to {ip}, which is not a public address"

    return None


def _canonical_page(url: str) -> str:
    """The document a URL points at, without the fragment or query that only decorate it."""
    parts = urlparse(url)
    return parts._replace(fragment="", query="").geturl()


def _is_new_page(url: str, pages_found: dict[str, str]) -> bool:
    """Whether this URL is a document the crawl has not already fetched.

    An in-page anchor is not a page. `href="#refund"` joins to `https://site/#refund`, which used
    to pass this filter, enter the frontier, and be registered by its link text as the canonical
    refund page, so the homepage was re-fetched and graded as the refund policy.
    """
    canonical = _canonical_page(url)
    seen = {_canonical_page(u) for u in pages_found}
    return canonical not in seen and canonical.rstrip("/") not in {s.rstrip("/") for s in seen}


def _classify_url_as_policy(url: str) -> str | None:
    path = urlparse(url).path.lower().rstrip("/")
    # Strip common page extensions so /terms.html matches /terms
    path_noext = path.removesuffix(".html").removesuffix(".php").removesuffix(".aspx")
    for ptype, patterns in POLICY_URL_PATTERNS.items():
        if any(path == p or path.endswith(p) or path_noext == p or path_noext.endswith(p) for p in patterns):
            return ptype
    return None


def _classify_link_text(text: str) -> str | None:
    text_lower = text.lower().strip()
    for ptype, patterns in POLICY_LINK_TEXT_PATTERNS.items():
        if any(p in text_lower for p in patterns):
            return ptype
    return None


_MAX_REDIRECT_HOPS = 5


async def _resolve_entry_url(request, url: str) -> tuple[str | None, str | None]:
    """Walk the entry URL's redirect chain by hand, checking every hop against the URL guard.

    The browser follows redirects inside its own network stack: a `context.route` handler is
    called for the navigation the crawler asked for and never for the hops that follow it, which
    was measured, not assumed. So a public site answering 302 to a metadata endpoint would be
    fetched with nothing having checked the address, and the contents would be handed back inside
    the report. Resolving the chain first means the refused request is never made at all.

    Returns (final url, None) or (None, reason it was refused).
    """
    current = url
    for _ in range(_MAX_REDIRECT_HOPS):
        reason = url_refusal_reason(current)
        if reason:
            return None, f"{current}: {reason}"
        try:
            response = await request.get(current, max_redirects=0, timeout=15000)
        except Exception:
            # Unreachable by this path. Let the browser try and report its own failure.
            return current, None
        if response.status not in (301, 302, 303, 307, 308):
            return current, None
        location = response.headers.get("location")
        if not location:
            return current, None
        current = urljoin(current, location)
    return None, f"{url}: more than {_MAX_REDIRECT_HOPS} redirects"


# A real sitemap is mostly products. Reading it costs a few requests and no rendering, but a
# compliance scan has no business walking tens of thousands of URLs.
_MAX_SITEMAP_DOCS = 5
_MAX_SITEMAP_URLS = 5000


async def _discover_from_sitemap(request, base_url: str, missing: list[str]) -> dict[str, str]:
    """Policy pages the site itself lists, for the types link discovery missed.

    Link discovery sees only what the homepage exposes, and probing guesses a handful of
    conventional paths. Neither finds a policy at `/info/shipping-policy`: nothing links it, and
    `/info` is not a prefix worth guessing. A sitemap names it outright.

    This is an extra source, not a replacement. One real storefront's sitemap listed products,
    collections and blog posts and no policy pages at all, because legal pages carry no SEO
    value, so a site that publishes no sitemap or omits its policies from it is the normal case
    rather than an error.
    """
    roots: list[str] = []
    try:
        robots = await request.get(urljoin(base_url, "/robots.txt"), timeout=10000)
        if robots.ok:
            for line in (await robots.text()).splitlines():
                if line.lower().startswith("sitemap:"):
                    roots.append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    roots.append(urljoin(base_url, "/sitemap.xml"))

    base_domain = _get_base_domain(base_url)
    found: dict[str, str] = {}
    seen_docs: set[str] = set()
    urls_seen = 0

    while roots and len(seen_docs) < _MAX_SITEMAP_DOCS and urls_seen < _MAX_SITEMAP_URLS:
        doc_url = roots.pop(0)
        if doc_url in seen_docs or _get_base_domain(doc_url) != base_domain:
            continue
        seen_docs.add(doc_url)
        try:
            response = await request.get(doc_url, timeout=15000)
            if not response.ok:
                continue
            soup = BeautifulSoup(await response.text(), "xml")
        except Exception:
            continue

        # A sitemapindex lists sitemaps; a urlset lists pages.
        is_index = soup.find("sitemapindex") is not None
        for loc in soup.find_all("loc"):
            value = loc.get_text(strip=True)
            if not value:
                continue
            urls_seen += 1
            if is_index:
                roots.append(value)
                continue
            if _get_base_domain(value) != base_domain:
                continue
            ptype = _classify_url_as_policy(value)
            if ptype in missing and ptype not in found:
                found[ptype] = _canonical_page(value)

    return found


def _probe_candidates(missing: list[str]) -> list[tuple[str, str]]:
    """Every (policy type, path) worth asking for, in declared order, capped."""
    candidates: list[tuple[str, str]] = []
    for ptype in missing:
        for pattern in POLICY_URL_PATTERNS.get(ptype, []):
            for prefix in _POLICY_PATH_PREFIXES:
                candidates.append((ptype, f"{prefix}{pattern}"))
    return candidates[:_MAX_PROBES]


async def _probe_for_policy_pages(request, base_url: str, missing: list[str]) -> dict[str, str]:
    """Ask for each undiscovered policy at the URLs the knowledge base says it lives at.

    Link discovery only sees what a homepage chooses to expose. Real stores link privacy and terms
    in the footer and leave refund and shipping to the checkout flow, so those pages were never
    fetched and the auditor graded whatever other page happened to hold a keyword, reporting a
    quality of 1 for a policy that scores 6 when the right page is read. The patterns to try were
    already declared on every check; they were only ever used to label links the crawler had
    already found, never to go looking. Every synthetic test site links all of its policies from
    the footer, which is why link discovery alone looked sufficient.

    A probe is a plain HTTP GET with no rendering, so this costs a fraction of a page load. Only
    types that link discovery missed are probed, so this can add a page but never displace one.
    """
    base_domain = _get_base_domain(base_url)
    candidates = _probe_candidates(missing)

    async def probe(ptype: str, path: str) -> tuple[str, str] | None:
        try:
            response = await request.get(urljoin(base_url, path), timeout=10000)
        except Exception:
            return None
        if not response.ok:
            return None
        # A site that answers an unknown path with a redirect to its homepage would otherwise
        # register the homepage as the refund policy. Requiring the URL we landed on to still read
        # as this policy type accepts /refund -> /policies/refund-policy and rejects /refund -> /.
        final = response.url
        if _get_base_domain(final) != base_domain:
            return None
        if _classify_url_as_policy(final) != ptype:
            return None
        return ptype, _canonical_page(final)

    results = await asyncio.gather(*(probe(t, p) for t, p in candidates))

    # Declared order decides, so /refund-policy beats /cancel when a site answers both.
    found: dict[str, str] = {}
    for hit in results:
        if hit and hit[0] not in found:
            found[hit[0]] = hit[1]
    return found


def _detect_tech_stack(html: str, headers: dict[str, str], cookies: list[str]) -> dict[str, list[str]]:
    """Match the crawled page against the detection rules in tech_stack_signatures.json.

    The rules live in the knowledge base rather than in this module so detection and the Razorpay
    recommendation for a stack cannot drift apart.
    """
    detected: dict[str, list[str]] = {}
    html_lower = html.lower()
    lowered_headers = {k.lower(): str(v).lower() for k, v in headers.items()}

    for stack, config in TECH_STACK_SIGNALS.items():
        signals = config.get("detection", {})
        evidence: list[str] = []

        for pattern in signals.get("html_contains", []):
            if pattern.lower() in html_lower:
                evidence.append(f"HTML contains '{pattern}'")

        meta = signals.get("meta")
        if meta:
            # Either a named meta tag is present, or its content starts with a known value
            prefix = meta.get("content_prefix", "")
            name = meta.get("name", "")
            if prefix and prefix.lower() in html_lower:
                evidence.append(f"Meta generator: {prefix}")
            elif name and f'name="{name.lower()}"' in html_lower:
                evidence.append(f"Meta tag: {name}")

        for hkey, hval in signals.get("headers", {}).items():
            if str(hval).lower() in lowered_headers.get(hkey.lower(), ""):
                evidence.append(f"Header {hkey}: {hval}")

        for cookie in signals.get("cookies", []):
            if any(cookie.lower() in c.lower() for c in cookies):
                evidence.append(f"Cookie: {cookie}")

        if evidence:
            detected[stack] = evidence

    if not detected:
        detected["static_html"] = ["No framework signals found"]

    return detected


async def crawl_website(url: str, max_pages: int = 20, timeout: int = 30) -> dict:
    base_domain = _get_base_domain(url)
    pages_found: dict[str, str] = {}
    http_headers: dict[str, dict] = {}
    scripts_all: list[dict] = []
    identified_pages: dict[str, str] = {}
    # Types identified by a URL that matches a declared pattern. Link text is weaker evidence: a
    # store selling "Return Gifts" at /collections/return-gifts reads as a refund policy, and that
    # shopping category was registered as the refund page and graded, while the real policy sat
    # unlinked at its conventional URL. A URL match, found or probed, overrides a text match.
    url_matched: set[str] = set()
    crawl_errors: list[str] = []
    all_links: list[str] = []
    tech_stack_signals: dict[str, list[str]] = {}

    # The exit stack closes the context and browser on every path, including exceptions
    async with async_playwright() as p, AsyncExitStack() as stack:
        browser: Browser = await p.chromium.launch(headless=True)
        stack.push_async_callback(browser.close)

        async def fetch_page(page_url: str) -> tuple[str, dict[str, str], str, list[str]]:
            # A context per page, not one for the crawl. Measured on a live Shopify store: sharing
            # a context returned the homepage at 1.6MB and then a 10KB, 26 word skeleton for every
            # policy page after it, because the storefront serves a client-routing shell to a
            # session that already has the app loaded. The engine graded those skeletons and
            # reported a perfectly good shipping policy as quality 1. A fresh context returned
            # every page in full. Neither a longer settle nor a browser user agent changed it, so
            # this is the session, not rendering time and not being taken for a bot.
            context = await browser.new_context(user_agent=_USER_AGENT)
            page = await context.new_page()
            response_headers: dict[str, str] = {}
            try:
                # `domcontentloaded` reliably fires. `networkidle` waits for 500ms of network
                # silence, which a real merchant site with analytics beacons, a chat widget and
                # polling never has, so waiting for it here spent the whole timeout and then
                # discarded a page whose HTML had been ready for seconds. Every synthetic test
                # site is static and goes idle at once, which is why this only failed off the lab.
                response = await page.goto(
                    page_url,
                    wait_until="domcontentloaded",
                    timeout=timeout * 1000,
                )
                if response:
                    response_headers = dict(response.headers)

                # Client-rendered content still needs a moment. Bounded, and failing to settle is
                # normal on the open web rather than an error, so the page is kept either way.
                try:
                    await page.wait_for_load_state("networkidle", timeout=_SETTLE_MS)
                except Exception:
                    pass

                html = await page.content()
                cookies = [c["name"] for c in await context.cookies()]
                return html, response_headers, page.url, cookies
            except Exception as e:
                crawl_errors.append(f"{page_url}: {e}")
                return "", {}, page_url, []
            finally:
                await page.close()
                await context.close()

        # Standalone request contexts, so neither resolving the redirect chain nor probing for
        # policy URLs spends the one anonymous request a session-aware site will answer in full.
        api = await p.request.new_context(user_agent=_USER_AGENT)
        stack.push_async_callback(api.dispose)

        # Fetch homepage, but resolve where it actually leads before pointing a browser at it.
        entry, refused = await _resolve_entry_url(api, url)
        if refused:
            crawl_errors.append(refused)
            entry = None

        html, headers, landed, cookies = (
            (await fetch_page(entry)) if entry else ("", {}, url, [])
        )
        if html:
            # A merchant who rebranded is still a merchant. wowskinscienceindia.com answers 301 to
            # buywow.in, and pinning the base domain to what was typed meant every absolute link on
            # the page read as off-domain and was thrown away: zero pages found, and the auditor
            # then graded the homepage as the refund policy and reported a better score than the
            # site deserved. The site being scanned is where the homepage actually resolved to.
            url = _canonical_page(landed) or url
            base_domain = _get_base_domain(url)
            pages_found[url] = html
            http_headers[url] = headers
            page_scripts = extract_scripts(html, url)
            scripts_all.extend(page_scripts)

            soup = BeautifulSoup(html, "lxml")

            # Collect all internal links
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                full_url = urljoin(url, href)
                if _get_base_domain(full_url) == base_domain and _is_new_page(full_url, pages_found):
                    full_url = _canonical_page(full_url)
                    if full_url in all_links:
                        continue
                    all_links.append(full_url)

                    ptype = _classify_url_as_policy(full_url)
                    if ptype and ptype not in url_matched:
                        identified_pages[ptype] = full_url
                        url_matched.add(ptype)

                    link_text = a_tag.get_text(strip=True)
                    ptype_text = _classify_link_text(link_text)
                    if ptype_text and ptype_text not in identified_pages:
                        identified_pages[ptype_text] = full_url

            # Detect tech stack from homepage
            tech_stack_signals = _detect_tech_stack(html, headers, cookies)

            # Whatever the homepage did not link at a declared URL: ask the site's own sitemap
            # first, since it names real URLs, then guess at conventional paths for the rest.
            def _record(discovered: dict[str, str]) -> None:
                for ptype, found_url in discovered.items():
                    identified_pages[ptype] = found_url
                    url_matched.add(ptype)
                    if found_url not in all_links:
                        all_links.append(found_url)

            missing = [p for p in POLICY_URL_PATTERNS if p not in url_matched]
            if missing:
                try:
                    _record(await _discover_from_sitemap(api, url, missing))
                except Exception as e:
                    crawl_errors.append(f"sitemap discovery: {e}")

            missing = [p for p in POLICY_URL_PATTERNS if p not in url_matched]
            if missing:
                try:
                    _record(await _probe_for_policy_pages(api, url, missing))
                except Exception as e:
                    crawl_errors.append(f"policy probe: {e}")

        # Crawl identified policy pages and a few more internal links
        priority_urls = list(identified_pages.values())
        extra_urls = [u for u in all_links if u not in priority_urls]
        to_crawl = priority_urls + extra_urls

        crawled = 0
        for page_url in to_crawl:
            if crawled >= max_pages - 1:
                break
            if not _is_new_page(page_url, pages_found):
                continue
            html, headers, _, _ = await fetch_page(page_url)
            if html:
                pages_found[page_url] = html
                http_headers[page_url] = headers
                page_scripts = extract_scripts(html, page_url)
                scripts_all.extend(page_scripts)
            crawled += 1

    # Deduplicate scripts by src
    seen_srcs: set[str] = set()
    unique_scripts: list[dict] = []
    for s in scripts_all:
        key = s.get("src") or f"inline_{len(unique_scripts)}"
        if key not in seen_srcs:
            seen_srcs.add(key)
            unique_scripts.append(s)

    return {
        "entry_url": url,
        "pages_found": pages_found,
        "scripts_found": unique_scripts,
        "http_headers": http_headers,
        "identified_pages": identified_pages,
        "tech_stack_signals": tech_stack_signals,
        "crawl_errors": crawl_errors,
        "pages_crawled": len(pages_found),
    }
