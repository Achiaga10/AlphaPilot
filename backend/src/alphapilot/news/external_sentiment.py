from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from time import monotonic
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from alphapilot.core.config import Settings


class ExternalSentimentFailureCode(StrEnum):
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    UNKNOWN_TICKER = "UNKNOWN_TICKER"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"


class AggregateEvidenceStrength(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


class AggregateSentimentEffect(StrEnum):
    POSITIVE_CONTEXT = "POSITIVE_CONTEXT"
    TARGETED_NEWS_REVIEW = "TARGETED_NEWS_REVIEW"
    MIXED_OR_NEUTRAL = "MIXED_OR_NEUTRAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class AggregateSentimentAssessment:
    strength: AggregateEvidenceStrength
    effect: AggregateSentimentEffect
    limitation: str | None


@dataclass(frozen=True)
class ExternalNewsSentimentSnapshot:
    """Provider-neutral aggregate News opinion with no trading authority."""

    ticker: str
    provider: str
    observed_at: datetime
    provider_timestamp: datetime | None
    period_start: date
    period_end: date
    sentiment_score: Decimal
    bullish_pct: Decimal | None
    bearish_pct: Decimal | None
    neutral_pct: Decimal | None
    mentions: int | None
    source_count: int | None
    buzz_score: Decimal | None
    trend: str | None


@dataclass(frozen=True)
class ExternalSentimentBatchResult:
    snapshots: tuple[ExternalNewsSentimentSnapshot, ...]
    failures: tuple[tuple[str, ExternalSentimentFailureCode], ...]
    request_count: int
    elapsed_seconds: float


class ExternalNewsSentimentProvider(Protocol):
    async def get_sentiment(
        self, ticker: str, *, start: date, end: date
    ) -> ExternalNewsSentimentSnapshot | None: ...

    async def get_sentiments(
        self, tickers: Sequence[str], *, start: date, end: date
    ) -> ExternalSentimentBatchResult: ...


class _AdanosStock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticker: str
    sentiment_score: Decimal
    bullish_pct: Decimal | None = None
    bearish_pct: Decimal | None = None
    mentions: int | None = None
    source_count: int | None = None
    buzz_score: Decimal | None = None
    trend: str | None = None


class _AdanosCompareResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_days: int
    stocks: list[_AdanosStock]


class AdanosNewsSentimentProvider:
    """Read-only POC adapter for Adanos aggregate stock-News sentiment."""

    provider_name = "ADANOS"
    max_batch_size = 10

    def __init__(
        self,
        config: Settings,
        client: httpx.AsyncClient | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_sentiment(
        self, ticker: str, *, start: date, end: date
    ) -> ExternalNewsSentimentSnapshot | None:
        result = await self.get_sentiments((ticker,), start=start, end=end)
        return result.snapshots[0] if result.snapshots else None

    async def get_sentiments(
        self, tickers: Sequence[str], *, start: date, end: date
    ) -> ExternalSentimentBatchResult:
        normalized = tuple(dict.fromkeys(item.strip().upper() for item in tickers if item.strip()))
        if not normalized:
            raise ValueError("tickers must not be empty")
        if len(normalized) > self.max_batch_size:
            raise ValueError("Adanos compare accepts at most 10 tickers")
        if start > end:
            raise ValueError("start must not be after end")
        if not self.config.ADANOS_API_KEY:
            return self._failure_result(
                normalized,
                ExternalSentimentFailureCode.AUTHENTICATION_FAILED,
                request_count=0,
            )

        started = monotonic()
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.ADANOS_TIMEOUT_SECONDS)
        try:
            response = await client.get(
                f"{self.config.ADANOS_BASE_URL.rstrip('/')}/news/stocks/v1/compare",
                headers={"X-API-Key": self.config.ADANOS_API_KEY},
                params={
                    "tickers": ",".join(normalized),
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                },
            )
            if response.status_code in {401, 403}:
                return self._failure_result(
                    normalized,
                    ExternalSentimentFailureCode.AUTHENTICATION_FAILED,
                    monotonic() - started,
                    request_count=1,
                )
            if response.status_code == 429:
                return self._failure_result(
                    normalized,
                    ExternalSentimentFailureCode.RATE_LIMITED,
                    monotonic() - started,
                    request_count=1,
                )
            response.raise_for_status()
            payload = _AdanosCompareResponse.model_validate(response.json())
            observed_at = self._clock()
            returned: dict[str, ExternalNewsSentimentSnapshot] = {}
            for stock in payload.stocks:
                ticker = stock.ticker.strip().upper()
                if ticker not in normalized or ticker in returned:
                    continue
                returned[ticker] = ExternalNewsSentimentSnapshot(
                    ticker=ticker,
                    provider=self.provider_name,
                    observed_at=observed_at,
                    provider_timestamp=None,
                    period_start=start,
                    period_end=end,
                    sentiment_score=stock.sentiment_score,
                    bullish_pct=stock.bullish_pct,
                    bearish_pct=stock.bearish_pct,
                    neutral_pct=None,
                    mentions=stock.mentions,
                    source_count=stock.source_count,
                    buzz_score=stock.buzz_score,
                    trend=stock.trend,
                )
            failures = tuple(
                (ticker, ExternalSentimentFailureCode.UNKNOWN_TICKER)
                for ticker in normalized
                if ticker not in returned
            )
            return ExternalSentimentBatchResult(
                snapshots=tuple(returned[ticker] for ticker in normalized if ticker in returned),
                failures=failures,
                request_count=1,
                elapsed_seconds=monotonic() - started,
            )
        except (ValidationError, TypeError, ValueError):
            return self._failure_result(
                normalized,
                ExternalSentimentFailureCode.MALFORMED_RESPONSE,
                monotonic() - started,
                request_count=1,
            )
        except httpx.HTTPError:
            return self._failure_result(
                normalized,
                ExternalSentimentFailureCode.PROVIDER_UNAVAILABLE,
                monotonic() - started,
                request_count=1,
            )
        finally:
            if owned:
                await client.aclose()

    @staticmethod
    def _failure_result(
        tickers: Sequence[str],
        code: ExternalSentimentFailureCode,
        elapsed_seconds: float = 0.0,
        *,
        request_count: int,
    ) -> ExternalSentimentBatchResult:
        return ExternalSentimentBatchResult(
            snapshots=(),
            failures=tuple((ticker, code) for ticker in tickers),
            request_count=request_count,
            elapsed_seconds=elapsed_seconds,
        )


def external_sentiment_has_trade_authority(snapshot: ExternalNewsSentimentSnapshot) -> bool:
    """Make the POC authority boundary explicit for callers and tests."""

    _ = snapshot
    return False


def assess_external_sentiment(
    snapshot: ExternalNewsSentimentSnapshot | None,
    *,
    as_of: datetime,
    fresh_hours: int = 24,
) -> AggregateSentimentAssessment:
    limitation = "PROVIDER_DATA_TIMESTAMP_UNAVAILABLE"
    if snapshot is None:
        return AggregateSentimentAssessment(
            AggregateEvidenceStrength.UNAVAILABLE,
            AggregateSentimentEffect.UNAVAILABLE,
            limitation,
        )
    observed_at = snapshot.observed_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    if as_of - observed_at > timedelta(hours=fresh_hours):
        return AggregateSentimentAssessment(
            AggregateEvidenceStrength.STALE,
            AggregateSentimentEffect.UNAVAILABLE,
            limitation,
        )
    if (snapshot.mentions or 0) < 5 or (snapshot.source_count or 0) < 2:
        return AggregateSentimentAssessment(
            AggregateEvidenceStrength.WEAK_EVIDENCE,
            AggregateSentimentEffect.MIXED_OR_NEUTRAL,
            limitation,
        )
    if snapshot.sentiment_score <= Decimal("-0.25") and (
        snapshot.bearish_pct or Decimal("0")
    ) >= Decimal("60"):
        effect = AggregateSentimentEffect.TARGETED_NEWS_REVIEW
    elif snapshot.sentiment_score >= Decimal("0.25") and (
        snapshot.bullish_pct or Decimal("0")
    ) >= Decimal("60"):
        effect = AggregateSentimentEffect.POSITIVE_CONTEXT
    else:
        effect = AggregateSentimentEffect.MIXED_OR_NEUTRAL
    return AggregateSentimentAssessment(
        AggregateEvidenceStrength.SUFFICIENT,
        effect,
        limitation,
    )
