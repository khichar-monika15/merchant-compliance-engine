from __future__ import annotations

from contextlib import AsyncExitStack
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Browser, async_playwright

from backend import knowledge
from backend.config import get_settings
from backend.tools.script_analyzer import extract_scripts


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
    crawl_errors: list[str] = []
    all_links: list[str] = []
    tech_stack_signals: dict[str, list[str]] = {}

    # The exit stack closes the context and browser on every path, including exceptions
    async with async_playwright() as p, AsyncExitStack() as stack:
        browser: Browser = await p.chromium.launch(headless=True)
        stack.push_async_callback(browser.close)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; MCIEBot/1.0; +https://github.com/khichar-monika15/merchant-compliance-engine)"
        )
        stack.push_async_callback(context.close)

        async def fetch_page(page_url: str) -> tuple[str, dict[str, str]]:
            page = await context.new_page()
            response_headers: dict[str, str] = {}
            try:
                response = await page.goto(
                    page_url,
                    wait_until="networkidle",
                    timeout=timeout * 1000,
                )
                if response:
                    response_headers = dict(response.headers)
                await page.wait_for_load_state("domcontentloaded")
                html = await page.content()
                return html, response_headers
            except Exception as e:
                crawl_errors.append(f"{page_url}: {e}")
                return "", {}
            finally:
                await page.close()

        # Fetch homepage
        html, headers = await fetch_page(url)
        if html:
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
                    if ptype and ptype not in identified_pages:
                        identified_pages[ptype] = full_url

                    link_text = a_tag.get_text(strip=True)
                    ptype_text = _classify_link_text(link_text)
                    if ptype_text and ptype_text not in identified_pages:
                        identified_pages[ptype_text] = full_url

            # Detect tech stack from homepage
            cookies = [c["name"] for c in await context.cookies()]
            tech_stack_signals = _detect_tech_stack(html, headers, cookies)

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
            html, headers = await fetch_page(page_url)
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
        "pages_found": pages_found,
        "scripts_found": unique_scripts,
        "http_headers": http_headers,
        "identified_pages": identified_pages,
        "tech_stack_signals": tech_stack_signals,
        "crawl_errors": crawl_errors,
        "pages_crawled": len(pages_found),
    }
