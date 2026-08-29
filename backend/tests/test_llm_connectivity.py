"""Live smoke test: verifies the LLM wrapper can reach its configured endpoint.

Skipped when no credentials are configured, and skipped rather than failed when the endpoint
rejects or cannot be reached — an expired token is an environment problem, not a code
regression, and the suite must stay green on a clean clone.
"""
import pytest

from backend.config import get_settings
from backend.tools.llm_client import _openai_complete, llm_complete


class TestDeterministicScoring:
    """The same site must score the same twice.

    Sampling defaulted to the provider's temperature (1.0), so a thin policy scored 3, then 5,
    then 6 across consecutive runs of the same fixture — the ground-truth harness caught it.
    """

    async def test_openai_path_requests_temperature_zero(self, monkeypatch):
        captured = {}

        class _Choice:
            message = type("M", (), {"content": "8"})()

        class _Completions:
            async def create(self, **kwargs):
                captured.update(kwargs)
                return type("R", (), {"choices": [_Choice()]})()

        class _Client:
            chat = type("C", (), {"completions": _Completions()})()

        monkeypatch.setattr("backend.tools.llm_client._openai_client", lambda: _Client())
        await _openai_complete("score this", max_tokens=10)
        assert captured.get("temperature") == 0

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


class TestTheReportedPathIsTheRealOne:
    """A transcript claiming the LLM path must mean the model actually answered.

    `_active_path` branched on `openai_api_key` alone while `llm_complete` requires the key AND
    the base URL, and returns "" rather than raising when either is missing. So with a key set
    and OPENAI_BASE_URL empty the probe raised nothing, and the banner printed "LLM-refined,
    reachable" over a run where every policy score had fallen back to rules. That is the exact
    false transcript the function's own docstring says it exists to prevent.
    """

    async def _path(self, monkeypatch, **env) -> str:
        from backend.config import get_settings
        from backend.tests.validate_ground_truth import _active_path

        for key, value in env.items():
            monkeypatch.setenv(key.upper(), value)
        get_settings.cache_clear()
        try:
            return await _active_path()
        finally:
            get_settings.cache_clear()

    async def test_a_key_without_a_base_url_is_not_the_llm_path(self, monkeypatch):
        path = await self._path(
            monkeypatch,
            openai_api_key="sk-present-but-useless",
            openai_base_url="",
            anthropic_api_key="",
        )
        assert "LLM-refined" not in path, (
            f"claimed the model path with no endpoint configured to reach: {path!r}"
        )
        assert "rule-only" in path, path

    async def test_an_empty_model_response_is_not_the_llm_path(self, monkeypatch):
        """A provider that returns nothing leaves every score on the rule fallback."""
        from backend.tests import validate_ground_truth as vgt

        async def silent(prompt, max_tokens=512):
            return ""

        monkeypatch.setattr("backend.tools.llm_client.llm_complete", silent)
        path = await self._path(
            monkeypatch,
            openai_api_key="sk-test",
            openai_base_url="https://example.invalid/v1",
            anthropic_api_key="",
        )
        assert "LLM-refined" not in path, (
            f"claimed the model path for a provider that returned nothing: {path!r}"
        )
