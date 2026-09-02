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
    AI_GENERATIVE_EXPLANATIONS_ENABLED: bool = True

    LIVE_QUOTE_MAX_AGE_SECONDS: int = 120

    DATABASE_URL: str = "postgresql+asyncpg://alphapilot:alphapilot@localhost:5432/alphapilot"
    TEST_DATABASE_URL: str | None = None

    REDIS_URL: str = "redis://localhost:6379"

    POLYGON_API_KEY: str = ""

    POLYGON_REQUESTS_PER_MINUTE: int = 5

    FINNHUB_API_KEY: str = ""

    ADANOS_API_KEY: str = ""
    ADANOS_BASE_URL: str = "https://api.adanos.org"
    ADANOS_TIMEOUT_SECONDS: float = 15.0

    OPENAI_API_KEY: str = ""

    NEWS_AI_CLASSIFIER_ENABLED: bool = True
    NEWS_AI_CLASSIFIER_PROVIDER: Literal["hosted"] = "hosted"
    NEWS_AI_CLASSIFIER_API_KEY: str = ""
    NEWS_AI_CLASSIFIER_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    NEWS_AI_CLASSIFIER_MODEL: str = "gemini-3.5-flash-lite"
    NEWS_AI_CLASSIFIER_TIMEOUT_SECONDS: float = 20.0
    NEWS_AI_CLASSIFIER_MIN_CONFIDENCE: float = 0.75
    NEWS_AI_CLASSIFIER_VERSION: str = "news-financial-impact-v1"
    NEWS_AI_CLASSIFIER_MAX_ATTEMPTS_PER_REFRESH: int = 10
    NEWS_AI_CLASSIFIER_DELAY_SECONDS: float = 0.25
    NEWS_COVERAGE_FRESH_HOURS: int = 24
    OLLAMA_NEWS_FALLBACK_ENABLED: bool = False

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
