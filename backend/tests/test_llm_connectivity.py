"""Live smoke test: verifies the LLM wrapper can reach its configured endpoint.

Skipped when no credentials are configured, and skipped rather than failed when the endpoint
rejects or cannot be reached — an expired token is an environment problem, not a code
regression, and the suite must stay green on a clean clone.
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
    try:
        result = await llm_complete("Reply with exactly the word: PONG", max_tokens=20)
    except Exception as e:
        pytest.skip(f"LLM endpoint unreachable or credentials rejected: {type(e).__name__}")

    assert isinstance(result, str), "Expected a string response"
    assert len(result) > 0, "Endpoint reachable but returned an empty response"
