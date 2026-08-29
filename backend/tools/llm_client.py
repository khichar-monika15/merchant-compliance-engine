"""Thin LLM wrapper, OpenAI-compatible (Bedrock mantle) or Anthropic direct API."""
from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings

_TIMEOUT_SECONDS = 60.0

# Compliance scoring has to be reproducible: the same site must score the same on two runs.
# At the providers' default temperature a thin policy scored 3, then 5, then 6.
_TEMPERATURE = 0


async def llm_complete(prompt: str, max_tokens: int = 512) -> str:
    """Send a single-turn prompt and return the text response. Empty string when unconfigured."""
    settings = get_settings()

    if settings.openai_api_key and settings.openai_base_url:
        return await _openai_complete(prompt, max_tokens)

    if settings.anthropic_api_key:
        return await _anthropic_complete(prompt, max_tokens)

    return ""


@lru_cache(maxsize=1)
def _openai_client():
    from openai import AsyncOpenAI

    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=_TIMEOUT_SECONDS,
    )


@lru_cache(maxsize=1)
def _anthropic_client():
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=get_settings().anthropic_api_key, timeout=_TIMEOUT_SECONDS)


async def _openai_complete(prompt: str, max_tokens: int) -> str:
    resp = await _openai_client().chat.completions.create(
        model=get_settings().llm_model,
        max_tokens=max_tokens,
        temperature=_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return (resp.choices[0].message.content or "").strip()


async def _anthropic_complete(prompt: str, max_tokens: int) -> str:
    resp = await _anthropic_client().messages.create(
        model=get_settings().anthropic_model,
        max_tokens=max_tokens,
        temperature=_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    return text.strip()
