from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    # OpenAI-compatible backend (e.g. AWS Bedrock mantle)
    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = "qwen.qwen3-32b"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    database_url: str = "sqlite+aiosqlite:///./mcie.db"
    log_level: str = "INFO"
    crawler_timeout: int = 30
    crawler_max_pages: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
