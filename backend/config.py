from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    # OpenAI-compatible backend (e.g. AWS Bedrock mantle)
    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = "qwen.qwen3-32b"
    anthropic_model: str = "claude-sonnet-4-6"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    database_url: str = "sqlite+aiosqlite:///./mcie.db"
    log_level: str = "INFO"
    crawler_timeout: int = 30
    crawler_max_pages: int = 20
    # The four demo sites are served on 127.0.0.1, so loopback has to be scannable locally. Turn
    # this off in any deployment: the crawler is a browser pointed at caller-supplied URLs.
    allow_loopback_scans: bool = True
    # Hard ceiling for one end-to-end scan, so a stalled crawl or LLM cannot pin a job forever
    pipeline_timeout: float = 300.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
