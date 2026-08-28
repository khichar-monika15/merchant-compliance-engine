from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.config import get_settings
from backend.models.schemas import AuditLogEntry, CrawlResult, EngineState, ScriptInfo
from backend.tools.crawler_tools import crawl_website


async def run(state: EngineState) -> dict:
    t0 = datetime.now(timezone.utc)
    settings = get_settings()
    url = str(state.merchant_input.website_url)

    try:
        raw = await crawl_website(
            url,
            max_pages=settings.crawler_max_pages,
            timeout=settings.crawler_timeout,
        )

        crawl_result = CrawlResult(
            pages_found={k: v for k, v in raw["pages_found"].items()},
            scripts_found=[ScriptInfo(**s) for s in raw["scripts_found"]],
            http_headers=raw["http_headers"],
            navigation_links=raw["navigation_links"],
            identified_pages=raw["identified_pages"],
            tech_stack_signals=raw["tech_stack_signals"],
            crawl_errors=raw["crawl_errors"],
            pages_crawled=raw["pages_crawled"],
            crawl_duration_seconds=raw["crawl_duration_seconds"],
        )

        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="WebCrawler",
            action=f"Crawled {url}",
            result=f"Found {crawl_result.pages_crawled} pages, {len(crawl_result.scripts_found)} scripts, "
                   f"{len(crawl_result.identified_pages)} policy pages identified",
            duration_ms=round(duration_ms, 1),
        )

        return {
            "crawl_result": crawl_result,
            "current_phase": "crawled",
            "audit_log": state.audit_log + [log],
        }

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        log = AuditLogEntry(
            timestamp=t0.isoformat(),
            agent="WebCrawler",
            action=f"Crawled {url}",
            result=f"ERROR: {e}",
            duration_ms=round(duration_ms, 1),
        )
        return {
            "current_phase": "crawl_failed",
            "errors": state.errors + [f"WebCrawler failed: {e}"],
            "audit_log": state.audit_log + [log],
        }
