"""Live smoke test: verifies the LLM wrapper can reach its configured endpoint.

Skipped when no credentials are configured, so a clean clone runs green.
"""
import pytest

from backend.config import get_settings
from backend.tools.llm_client import llm_complete

_settings = get_settings()
_has_credentials = bool(
    (_settings.openai_api_key and _settings.openai_base_url) or _settings.anthropic_api_key
)


@pytest.mark.skipif(not _has_credentials, reason="No LLM credentials configured")
async def test_llm_responds():
    result = await llm_complete("Reply with exactly the word: PONG", max_tokens=20)
    assert isinstance(result, str), "Expected a string response"
    assert len(result) > 0, "Got empty response from LLM"
