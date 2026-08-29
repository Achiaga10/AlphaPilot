from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AlphaPilot"

    VERSION: str = "1.0.0"

    DEBUG: bool = True

    LOG_LEVEL: str = "INFO"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    ADMIN_TOOLS_ENABLED: bool = False

    DAILY_MARKET_SYNC_ENABLED: bool = False

    AI_COPILOT_ENABLED: bool = False
    AI_PROVIDER: Literal["ollama"] = "ollama"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = ""
    OLLAMA_TIMEOUT_SECONDS: float = 30.0

    DATABASE_URL: str = "postgresql+asyncpg://alphapilot:alphapilot@localhost:5432/alphapilot"
    TEST_DATABASE_URL: str | None = None

    REDIS_URL: str = "redis://localhost:6379"

    POLYGON_API_KEY: str = ""

    POLYGON_REQUESTS_PER_MINUTE: int = 5

    FINNHUB_API_KEY: str = ""

    OPENAI_API_KEY: str = ""

    WIKIMEDIA_USER_AGENT: str = ""

    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_DATA_FEED: Literal["iex", "sip"] = "iex"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
