from datetime import UTC, datetime

import httpx
import pytest

from alphapilot.core.config import Settings
from alphapilot.news.classifier import HostedNewsClassifier
from alphapilot.news.models import ClassificationStatus, NormalizedNewsArticle


def article() -> NormalizedNewsArticle:
    return NormalizedNewsArticle(
        ticker="APA",
        company_name="APA Corporation",
        provider="FINNHUB",
        provider_article_id="1",
        canonical_url="https://example.com/a",
        headline="APA cuts full-year revenue guidance materially",
        summary="Management reduced its expected annual revenue range.",
        source="Reuters",
        published_at=datetime(2026, 8, 31, tzinfo=UTC),
        received_at=datetime(2026, 8, 31, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_hosted_classifier_requires_strict_validated_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert "responseJsonSchema" in body
        assert "portfolio" not in body.lower()
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"event_type":"GUIDANCE","impact":"NEGATIVE",'
                                        '"severity":"HIGH","confidence":0.91,'
                                        '"reason":"Forward revenue expectations were reduced."}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    config = Settings(NEWS_AI_CLASSIFIER_API_KEY="test-key", DEBUG=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await HostedNewsClassifier(config, client).classify(article())
    assert result.status is ClassificationStatus.CLASSIFIED
    assert result.output is not None
    assert result.output.event_type.value == "GUIDANCE"


@pytest.mark.asyncio
async def test_invalid_output_is_invalid_and_never_parsed_as_trade_action() -> None:
    response = httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": '{"action":"SELL"}'}]}}]},
    )
    config = Settings(NEWS_AI_CLASSIFIER_API_KEY="test-key", DEBUG=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
        result = await HostedNewsClassifier(config, client).classify(article())
    assert result.status is ClassificationStatus.INVALID
    assert result.output is None


@pytest.mark.asyncio
async def test_missing_key_and_rate_limit_are_explicit() -> None:
    unavailable = await HostedNewsClassifier(
        Settings(DEBUG=False, NEWS_AI_CLASSIFIER_API_KEY="", _env_file=None)
    ).classify(article())
    assert unavailable.status is ClassificationStatus.UNAVAILABLE

    config = Settings(NEWS_AI_CLASSIFIER_API_KEY="test-key", DEBUG=False)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        limited = await HostedNewsClassifier(config, client).classify(article())
    assert limited.status is ClassificationStatus.RATE_LIMITED
