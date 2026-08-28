"""Thin LLM wrapper — OpenAI-compatible (Bedrock mantle) or Anthropic direct API."""
from __future__ import annotations

from backend.config import get_settings


async def llm_complete(prompt: str, max_tokens: int = 512) -> str:
    """Send a single-turn prompt and return the text response."""
    settings = get_settings()

    if settings.openai_api_key and settings.openai_base_url:
        return await _openai_complete(prompt, max_tokens)

    if settings.anthropic_api_key:
        return await _anthropic_complete(prompt, max_tokens)

    return ""


async def _openai_complete(prompt: str, max_tokens: int) -> str:
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return (resp.choices[0].message.content or "").strip()


async def _anthropic_complete(prompt: str, max_tokens: int) -> str:
    from anthropic import AsyncAnthropic

    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
