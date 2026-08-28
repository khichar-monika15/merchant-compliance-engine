from __future__ import annotations

import asyncio
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Browser, async_playwright

from backend.tools.script_analyzer import extract_scripts

POLICY_URL_PATTERNS: dict[str, list[str]] = {
    "refund": ["/refund", "/return", "/cancellation", "/refund-policy", "/return-policy", "/cancel"],
    "privacy": ["/privacy", "/privacy-policy", "/data-policy", "/data-protection"],
    "terms": ["/terms", "/tos", "/terms-and-conditions", "/terms-of-service", "/terms-of-use"],
    "contact": ["/contact", "/contact-us", "/reach-us", "/get-in-touch", "/support"],
    "checkout": ["/checkout", "/cart", "/payment", "/pay", "/order"],
}

POLICY_LINK_TEXT_PATTERNS: dict[str, list[str]] = {
    "refund": ["refund", "return", "cancellation", "money back", "cancel"],
    "privacy": ["privacy", "data policy", "data protection"],
    "terms": ["terms", "conditions", "terms of service", "tos"],
    "contact": ["contact", "reach us", "get in touch", "help", "support"],
}

TECH_STACK_SIGNALS: dict[str, dict] = {
    "shopify": {
        "html_contains": ["myshopify.com", "Shopify.theme", "shopify-section", "cdn.shopify.com"],
        "meta_name": "shopify-checkout-api-token",
    },
    "wordpress": {
        "html_contains": ["wp-content", "wp-includes"],
        "meta": {"name": "generator", "content_prefix": "WordPress"},
    },
    "woocommerce": {
        "html_contains": ["woocommerce", "wc-", "class=\"woo"],
    },
    "nextjs": {
        "html_contains": ["_next/static", "__NEXT_DATA__", "_next/chunks"],
        "header": {"x-powered-by": "Next.js"},
    },
    "react": {
        "html_contains": ["react-dom", "data-reactroot", "__react", "ReactDOM"],
    },
    "vue_nuxt": {
        "html_contains": ["__nuxt", "vue-", "data-v-"],
    },
    "django": {
        "html_contains": ["csrfmiddlewaretoken"],
    },
    "laravel": {
        "cookie": "laravel_session",
    },
    "static_html": {},
}


def _get_base_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _classify_url_as_policy(url: str) -> str | None:
    path = urlparse(url).path.lower().rstrip("/")
    for ptype, patterns in POLICY_URL_PATTERNS.items():
        if any(path == p or path.endswith(p) for p in patterns):
            return ptype
    return None


def _classify_link_text(text: str) -> str | None:
    text_lower = text.lower().strip()
    for ptype, patterns in POLICY_LINK_TEXT_PATTERNS.items():
        if any(p in text_lower for p in patterns):
            return ptype
    return None


def _detect_tech_stack(html: str, headers: dict[str, str], cookies: list[str]) -> dict[str, list[str]]:
    detected: dict[str, list[str]] = {}
    html_lower = html.lower()
    lowered_headers = {k.lower(): v.lower() for k, v in headers.items()}

    for stack, signals in TECH_STACK_SIGNALS.items():
        evidence: list[str] = []

        for pattern in signals.get("html_contains", []):
            if pattern.lower() in html_lower:
                evidence.append(f"HTML contains '{pattern}'")

        if "meta" in signals:
            meta_info = signals["meta"]
            if meta_info.get("content_prefix", "").lower() in html_lower:
                evidence.append(f"Meta generator: {meta_info['content_prefix']}")

        if "header" in signals:
            for hkey, hval in signals["header"].items():
                if hkey in lowered_headers and hval.lower() in lowered_headers[hkey]:
                    evidence.append(f"Header {hkey}: {hval}")

        if "cookie" in signals:
            if any(signals["cookie"] in c for c in cookies):
                evidence.append(f"Cookie: {signals['cookie']}")

        if evidence:
            detected[stack] = evidence

    if not detected:
        detected["static_html"] = ["No framework signals found"]

    return detected


async def crawl_website(url: str, max_pages: int = 20, timeout: int = 30) -> dict:
    start = time.time()
    base_domain = _get_base_domain(url)
    pages_found: dict[str, str] = {}
    http_headers: dict[str, dict] = {}
    scripts_all: list[dict] = []
    identified_pages: dict[str, str] = {}
    crawl_errors: list[str] = []
    all_links: list[str] = []
    tech_stack_signals: dict[str, list[str]] = {}

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; MCIEBot/1.0; +https://github.com/khichar-monika15/merchant-compliance-engine)"
        )

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
                if _get_base_domain(full_url) == base_domain and full_url not in pages_found:
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
            if crawled >= max_pages - 1 or page_url in pages_found:
                continue
            html, headers = await fetch_page(page_url)
            if html:
                pages_found[page_url] = html
                http_headers[page_url] = headers
                page_scripts = extract_scripts(html, page_url)
                scripts_all.extend(page_scripts)
            crawled += 1

        await browser.close()

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
        "navigation_links": list(set(all_links))[:100],
        "identified_pages": identified_pages,
        "tech_stack_signals": tech_stack_signals,
        "crawl_errors": crawl_errors,
        "pages_crawled": len(pages_found),
        "crawl_duration_seconds": round(time.time() - start, 2),
    }
