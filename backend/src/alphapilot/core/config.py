from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AlphaPilot"

    VERSION: str = "1.0.0"

    DEBUG: bool = True

    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://alphapilot:alphapilot@localhost:5432/alphapilot"
    TEST_DATABASE_URL: str | None = None

    REDIS_URL: str = "redis://localhost:6379"

    POLYGON_API_KEY: str = ""

    FINNHUB_API_KEY: str = ""

    OPENAI_API_KEY: str = ""

    WIKIMEDIA_USER_AGENT: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
