"""Test Claude models via Anthropic messages format on Bedrock mantle."""
import asyncio, os, httpx
import backend.config as _cfg; _cfg.get_settings.cache_clear()
from backend.config import get_settings


async def main():
    s = get_settings()
    # Anthropic-format endpoint: strip /v1 suffix from base URL
    base = s.openai_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]

    url = f"{base}/v1/messages"
    headers = {
        "Authorization": f"Bearer {s.openai_api_key}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": "anthropic.claude-haiku-4-5",
        "max_tokens": 20,
        "messages": [{"role": "user", "content": "Reply with exactly: HELLO"}],
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:300]}")


asyncio.run(main())
