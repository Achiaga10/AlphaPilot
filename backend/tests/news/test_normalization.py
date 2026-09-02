from datetime import UTC, datetime

from alphapilot.news.models import NormalizedNewsArticle
from alphapilot.news.service import article_fingerprint, canonicalize_url


def test_url_canonicalization_removes_tracking_and_fingerprint_is_deterministic() -> None:
    assert canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&b=2") == (
        "https://example.com/a?b=2"
    )
    item = NormalizedNewsArticle(
        ticker="apa",
        company_name=None,
        provider="FINNHUB",
        provider_article_id=None,
        canonical_url=None,
        headline="  Company   announces results ",
        summary=None,
        source="Reuters",
        published_at=datetime(2026, 9, 1, tzinfo=UTC),
        received_at=datetime(2026, 9, 1, 1, tzinfo=UTC),
    )
    assert article_fingerprint(item) == article_fingerprint(item)
