from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from alphapilot.core.config import Settings
from alphapilot.news.external_sentiment import (
    AdanosNewsSentimentProvider,
    AggregateEvidenceStrength,
    AggregateSentimentEffect,
    ExternalNewsSentimentSnapshot,
    ExternalSentimentFailureCode,
    assess_external_sentiment,
    external_sentiment_has_trade_authority,
)

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
START = date(2026, 8, 26)
END = date(2026, 9, 1)


def config(key: str = "test-key") -> Settings:
    return Settings(ADANOS_API_KEY=key, ADANOS_BASE_URL="https://adanos.test")


@pytest.mark.asyncio
async def test_adanos_compare_normalizes_success_and_missing_optional_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/news/stocks/v1/compare"
        assert request.url.params["tickers"] == "AAPL,MSFT"
        assert request.headers["X-API-Key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "period_days": 7,
                "stocks": [
                    {
                        "ticker": "AAPL",
                        "sentiment_score": 0.42,
                        "bullish_pct": 71.5,
                        "bearish_pct": 28.5,
                        "mentions": 81,
                        "source_count": 12,
                        "buzz_score": 55.2,
                        "trend": "RISING",
                    },
                    {"ticker": "MSFT", "sentiment_score": -0.1},
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AdanosNewsSentimentProvider(
            config(), client, clock=lambda: NOW
        ).get_sentiments((" aapl ", "MSFT", "AAPL"), start=START, end=END)

    assert result.request_count == 1
    assert result.failures == ()
    assert [item.ticker for item in result.snapshots] == ["AAPL", "MSFT"]
    apple, microsoft = result.snapshots
    assert str(apple.sentiment_score) == "0.42"
    assert apple.source_count == 12
    assert apple.provider_timestamp is None
    assert microsoft.bullish_pct is None
    assert microsoft.neutral_pct is None


@pytest.mark.asyncio
async def test_adanos_unknown_ticker_maps_missing_batch_member() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"period_days": 7, "stocks": []})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await AdanosNewsSentimentProvider(config(), client).get_sentiments(
            ("ZZZZ",), start=START, end=END
        )
    assert result.failures == (("ZZZZ", ExternalSentimentFailureCode.UNKNOWN_TICKER),)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ExternalSentimentFailureCode.AUTHENTICATION_FAILED),
        (429, ExternalSentimentFailureCode.RATE_LIMITED),
    ],
)
async def test_adanos_maps_authentication_and_rate_limit(
    status: int, expected: ExternalSentimentFailureCode
) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await AdanosNewsSentimentProvider(config(), client).get_sentiments(
            ("AAPL",), start=START, end=END
        )
    assert result.failures[0] == ("AAPL", expected)


@pytest.mark.asyncio
async def test_adanos_malformed_payload_fails_closed() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"period_days": 7, "stocks": "wrong"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await AdanosNewsSentimentProvider(config(), client).get_sentiments(
            ("AAPL",), start=START, end=END
        )
    assert result.failures[0][1] is ExternalSentimentFailureCode.MALFORMED_RESPONSE


@pytest.mark.asyncio
async def test_adanos_missing_key_never_sends_or_leaks_secret() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AdanosNewsSentimentProvider(config(""), client).get_sentiments(
            ("AAPL",), start=START, end=END
        )
    assert not called
    assert result.failures[0][1] is ExternalSentimentFailureCode.AUTHENTICATION_FAILED
    assert "test-key" not in repr(result)


@pytest.mark.asyncio
async def test_external_sentiment_has_no_direct_trade_authority() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "period_days": 7,
                "stocks": [{"ticker": "AAPL", "sentiment_score": -1}],
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await AdanosNewsSentimentProvider(config(), client).get_sentiment(
            "AAPL", start=START, end=END
        )
    assert snapshot is not None
    assert external_sentiment_has_trade_authority(snapshot) is False


@pytest.mark.asyncio
async def test_adanos_ticker_mapping_and_batch_limit_are_deterministic() -> None:
    provider = AdanosNewsSentimentProvider(config())
    with pytest.raises(ValueError, match="at most 10"):
        await provider.get_sentiments(tuple(f"T{i}" for i in range(11)), start=START, end=END)


def snapshot(
    *,
    score: str,
    bullish: str,
    bearish: str,
    mentions: int,
    sources: int,
    observed_at: datetime = NOW,
    trend: str = "stable",
) -> ExternalNewsSentimentSnapshot:
    return ExternalNewsSentimentSnapshot(
        ticker="APA",
        provider="ADANOS",
        observed_at=observed_at,
        provider_timestamp=None,
        period_start=START,
        period_end=END,
        sentiment_score=Decimal(score),
        bullish_pct=Decimal(bullish),
        bearish_pct=Decimal(bearish),
        neutral_pct=None,
        mentions=mentions,
        source_count=sources,
        buzz_score=None,
        trend=trend,
    )


@pytest.mark.parametrize(
    ("value", "strength", "effect"),
    [
        (
            snapshot(score="0.6", bullish="80", bearish="5", mentions=100, sources=20),
            AggregateEvidenceStrength.SUFFICIENT,
            AggregateSentimentEffect.POSITIVE_CONTEXT,
        ),
        (
            snapshot(score="-0.6", bullish="5", bearish="80", mentions=100, sources=20),
            AggregateEvidenceStrength.SUFFICIENT,
            AggregateSentimentEffect.TARGETED_NEWS_REVIEW,
        ),
        (
            snapshot(score="0", bullish="45", bearish="45", mentions=100, sources=20),
            AggregateEvidenceStrength.SUFFICIENT,
            AggregateSentimentEffect.MIXED_OR_NEUTRAL,
        ),
        (
            snapshot(score="0.9", bullish="100", bearish="0", mentions=1, sources=1),
            AggregateEvidenceStrength.WEAK_EVIDENCE,
            AggregateSentimentEffect.MIXED_OR_NEUTRAL,
        ),
        (
            snapshot(score="-0.9", bullish="0", bearish="100", mentions=1, sources=1),
            AggregateEvidenceStrength.WEAK_EVIDENCE,
            AggregateSentimentEffect.MIXED_OR_NEUTRAL,
        ),
        (
            snapshot(
                score="0.4", bullish="70", bearish="5", mentions=20, sources=5, trend="falling"
            ),
            AggregateEvidenceStrength.SUFFICIENT,
            AggregateSentimentEffect.POSITIVE_CONTEXT,
        ),
        (
            snapshot(
                score="-0.4", bullish="5", bearish="70", mentions=20, sources=5, trend="rising"
            ),
            AggregateEvidenceStrength.SUFFICIENT,
            AggregateSentimentEffect.TARGETED_NEWS_REVIEW,
        ),
    ],
)
def test_predeclared_aggregate_policy(value, strength, effect) -> None:
    assessment = assess_external_sentiment(value, as_of=NOW)
    assert assessment.strength is strength
    assert assessment.effect is effect
    assert assessment.limitation == "PROVIDER_DATA_TIMESTAMP_UNAVAILABLE"
    assert external_sentiment_has_trade_authority(value) is False


def test_missing_and_old_aggregate_never_fabricate_neutral() -> None:
    missing = assess_external_sentiment(None, as_of=NOW)
    old = assess_external_sentiment(
        snapshot(
            score="0",
            bullish="50",
            bearish="50",
            mentions=10,
            sources=3,
            observed_at=NOW - timedelta(days=2),
        ),
        as_of=NOW,
    )
    assert missing.effect is AggregateSentimentEffect.UNAVAILABLE
    assert old.strength is AggregateEvidenceStrength.STALE
