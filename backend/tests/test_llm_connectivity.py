"""Quick smoke test: verifies the LLM wrapper can reach Bedrock."""
import os
import pytest

# Override before any config import so lru_cache picks it up
os.environ["LLM_MODEL"] = "qwen.qwen3-32b"

import backend.config as _cfg
_cfg.get_settings.cache_clear()

from backend.tools.llm_client import llm_complete


@pytest.mark.asyncio
async def test_llm_responds():
    result = await llm_complete("Reply with exactly the word: PONG", max_tokens=20)
    assert isinstance(result, str), "Expected a string response"
    assert len(result) > 0, "Got empty response from LLM"
    print(f"\nLLM said: {result!r}")
