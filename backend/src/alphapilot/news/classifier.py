from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import httpx
from pydantic import ValidationError

from alphapilot.core.config import Settings
from alphapilot.news.models import (
    ClassificationStatus,
    NewsClassificationOutput,
    NormalizedNewsArticle,
)


@dataclass(frozen=True)
class ClassificationAttempt:
    status: ClassificationStatus
    provider: str
    model: str
    version: str
    classified_at: datetime
    output: NewsClassificationOutput | None = None
    failure_code: str | None = None
    retry_after_seconds: int | None = None


class NewsClassifierProvider(Protocol):
    @property
    def primary_identity(self) -> tuple[str, str, str]: ...

    async def classify(self, article: NormalizedNewsArticle) -> ClassificationAttempt: ...


SYSTEM_INSTRUCTION = """You classify the likely financial/business impact of one factual
company-news item. Return only the required JSON fields. Interpret the event rather than
headline tone. Layoffs may be mixed. Never recommend or mention BUY, SELL, HOLD, position
size, allocation, entry, exit, stop, or target prices. Use UNKNOWN when facts are
insufficient."""


def classification_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": [
                    "EARNINGS",
                    "GUIDANCE",
                    "M_AND_A",
                    "ANALYST_RATING",
                    "MANAGEMENT",
                    "LEGAL_REGULATORY",
                    "ACCOUNTING",
                    "CAPITAL_RAISE",
                    "BUYBACK_DIVIDEND",
                    "PRODUCT",
                    "CUSTOMER_CONTRACT",
                    "SEC_FILING",
                    "BANKRUPTCY_DISTRESS",
                    "DELISTING",
                    "TRADING_HALT",
                    "CYBERSECURITY",
                    "LAYOFFS_COST_REDUCTION",
                    "MACRO_SECTOR",
                    "OTHER",
                    "UNKNOWN",
                ],
            },
            "impact": {
                "type": "string",
                "enum": ["POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "UNKNOWN"],
            },
            "severity": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "SEVERE", "UNKNOWN"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "maxLength": 500},
        },
        "required": ["event_type", "impact", "severity", "confidence", "reason"],
        "additionalProperties": False,
    }


class HostedNewsClassifier:
    """Google Gemini hosted classifier using strict JSON Schema output."""

    provider_name = "GOOGLE_GEMINI"

    def __init__(self, config: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    @property
    def primary_identity(self) -> tuple[str, str, str]:
        return (
            self.provider_name,
            self.config.NEWS_AI_CLASSIFIER_MODEL,
            self.config.NEWS_AI_CLASSIFIER_VERSION,
        )

    async def classify(self, article: NormalizedNewsArticle) -> ClassificationAttempt:
        now = datetime.now(UTC)

        def attempt(
            status: ClassificationStatus,
            *,
            output: NewsClassificationOutput | None = None,
            failure_code: str | None = None,
            retry_after_seconds: int | None = None,
        ) -> ClassificationAttempt:
            return ClassificationAttempt(
                status=status,
                provider=self.provider_name,
                model=self.config.NEWS_AI_CLASSIFIER_MODEL,
                version=self.config.NEWS_AI_CLASSIFIER_VERSION,
                classified_at=now,
                output=output,
                failure_code=failure_code,
                retry_after_seconds=retry_after_seconds,
            )

        if not self.config.NEWS_AI_CLASSIFIER_ENABLED or not self.config.NEWS_AI_CLASSIFIER_API_KEY:
            return attempt(
                ClassificationStatus.UNAVAILABLE,
                failure_code="HOSTED_API_KEY_NOT_CONFIGURED",
            )
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": self._article_text(article)}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": classification_json_schema(),
            },
        }
        owned = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.config.NEWS_AI_CLASSIFIER_TIMEOUT_SECONDS
        )
        try:
            response = await client.post(
                f"{self.config.NEWS_AI_CLASSIFIER_BASE_URL}/models/"
                f"{self.config.NEWS_AI_CLASSIFIER_MODEL}:generateContent",
                params={"key": self.config.NEWS_AI_CLASSIFIER_API_KEY},
                json=payload,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                return attempt(
                    ClassificationStatus.RATE_LIMITED,
                    failure_code="HOSTED_RATE_LIMITED",
                    retry_after_seconds=(
                        int(retry_after) if retry_after and retry_after.isdigit() else None
                    ),
                )
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            raw = data["candidates"][0]["content"]["parts"][0]["text"]
            output = NewsClassificationOutput.model_validate(json.loads(str(raw)))
            return attempt(ClassificationStatus.CLASSIFIED, output=output)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            return attempt(
                ClassificationStatus.UNAVAILABLE,
                failure_code="HOSTED_REQUEST_FAILED",
            )
        except ValidationError:
            return attempt(
                ClassificationStatus.INVALID,
                failure_code="INVALID_STRUCTURED_OUTPUT",
            )
        finally:
            if owned:
                await client.aclose()

    @staticmethod
    def _article_text(article: NormalizedNewsArticle) -> str:
        factual = {
            "ticker": article.ticker,
            "company_name": article.company_name,
            "headline": article.headline,
            "provider_summary": article.summary,
            "source": article.source,
            "published_at": article.published_at.isoformat(),
        }
        return json.dumps(factual, ensure_ascii=False, separators=(",", ":"))


class OllamaNewsClassifier:
    provider_name = "OLLAMA"

    def __init__(self, config: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client

    @property
    def primary_identity(self) -> tuple[str, str, str]:
        return (
            self.provider_name,
            self.config.OLLAMA_MODEL,
            self.config.NEWS_AI_CLASSIFIER_VERSION,
        )

    async def classify(self, article: NormalizedNewsArticle) -> ClassificationAttempt:
        now = datetime.now(UTC)

        def attempt(
            status: ClassificationStatus,
            *,
            output: NewsClassificationOutput | None = None,
            failure_code: str | None = None,
        ) -> ClassificationAttempt:
            return ClassificationAttempt(
                status=status,
                provider=self.provider_name,
                model=self.config.OLLAMA_MODEL,
                version=self.config.NEWS_AI_CLASSIFIER_VERSION,
                classified_at=now,
                output=output,
                failure_code=failure_code,
            )

        if not self.config.OLLAMA_NEWS_FALLBACK_ENABLED or not self.config.OLLAMA_MODEL:
            return attempt(
                ClassificationStatus.UNAVAILABLE,
                failure_code="OLLAMA_FALLBACK_DISABLED",
            )
        payload = {
            "model": self.config.OLLAMA_MODEL,
            "stream": False,
            "format": classification_json_schema(),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": HostedNewsClassifier._article_text(article)},
            ],
        }
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.OLLAMA_TIMEOUT_SECONDS)
        try:
            response = await client.post(f"{self.config.OLLAMA_BASE_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            output = NewsClassificationOutput.model_validate_json(data["message"]["content"])
            return attempt(ClassificationStatus.CLASSIFIED, output=output)
        except ValidationError:
            return attempt(
                ClassificationStatus.INVALID,
                failure_code="INVALID_STRUCTURED_OUTPUT",
            )
        except (httpx.HTTPError, KeyError, TypeError):
            return attempt(
                ClassificationStatus.UNAVAILABLE,
                failure_code="OLLAMA_REQUEST_FAILED",
            )
        finally:
            if owned:
                await client.aclose()


class FallbackNewsClassifier:
    def __init__(
        self, primary: NewsClassifierProvider, fallback: NewsClassifierProvider | None
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    @property
    def primary_identity(self) -> tuple[str, str, str]:
        return self.primary.primary_identity

    async def classify(self, article: NormalizedNewsArticle) -> ClassificationAttempt:
        result = await self.primary.classify(article)
        if result.status is ClassificationStatus.CLASSIFIED or self.fallback is None:
            return result
        return await self.fallback.classify(article)
