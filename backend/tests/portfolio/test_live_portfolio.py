from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from alphapilot.api.routes.portfolio import get_live_portfolio_service
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.research_portfolio import PaperValidationRecord
from alphapilot.main import app
from alphapilot.market.live import (
    LiveBriefReadiness,
    LiveMonitoringStatus,
    LiveQuoteFreshness,
    ProviderLiveSnapshot,
)
from alphapilot.services.live_portfolio import LiveMarketCache, LivePortfolioService
from alphapilot.services.research_portfolio import ResearchPortfolioService
from alphapilot.strategy.indicators import calculate_ema_series


class FakeLiveProvider:
    provider_name = "fake-live"
    feed = SimpleNamespace(value="iex")

    def __init__(self, snapshots: dict[str, ProviderLiveSnapshot]) -> None:
        self.snapshots = snapshots
        self.requests: list[list[str]] = []

    async def get_live_snapshots(self, tickers: list[str]) -> dict[str, ProviderLiveSnapshot]:
        self.requests.append(tickers)
        return self.snapshots


async def _portfolio(db_session, *, second: bool = False):
    companies = [Company(ticker="AAA", name="Alpha", exchange="NYSE", sector="Technology")]
    if second:
        companies.append(Company(ticker="BBB", name="Beta", exchange="NYSE", sector="Technology"))
    db_session.add_all(companies)
    await db_session.commit()
    service = ResearchPortfolioService(db_session)
    portfolio = await service.initialize(starting_cash=Decimal("10000"))
    for index, company in enumerate(companies):
        await service.buy(
            portfolio_id=portfolio.id,
            expected_revision=index,
            ticker=company.ticker,
            quantity=2,
            execution_price=Decimal("100"),
            trading_day=date(2025, 1, 2),
            strategy="ema20-pullback",
            profile_id="ema20-pullback-v1",
            profile_version=1,
            profile_snapshot={"profile_id": "ema20-pullback-v1", "version": 1},
            selection_policy="relative-strength-20",
            decision="BUY",
            reason="BUY_APPROVED",
            modeled_risk_dollars=Decimal("20"),
            action_id=f"buy-{company.ticker}",
        )
        start = date(2025, 1, 1)
        db_session.add_all(
            [
                DailyCandle(
                    company_id=company.id,
                    trading_day=start + timedelta(days=day),
                    open=Decimal(100 + day) / Decimal("2"),
                    high=Decimal(102 + day) / Decimal("2"),
                    low=Decimal(98 + day) / Decimal("2"),
                    close=Decimal(100 + day) / Decimal("2"),
                    volume=1000 + day,
                )
                for day in range(160)
            ]
        )
    await db_session.commit()
    return portfolio, companies


def _snapshot(ticker: str, price: str, timestamp: datetime) -> ProviderLiveSnapshot:
    return ProviderLiveSnapshot(
        ticker,
        timestamp.date(),
        Decimal(price),
        Decimal("100"),
        Decimal("110"),
        Decimal("75"),
        5000,
        Decimal("129.5"),
        timestamp,
        "fake-live",
        "iex",
    )


@pytest.mark.asyncio
async def test_live_refresh_is_open_position_only_ephemeral_and_deterministic(db_session) -> None:
    portfolio, companies = await _portfolio(db_session)
    now = datetime(2025, 6, 10, 15, 0, tzinfo=UTC)
    provider = FakeLiveProvider({"AAA": _snapshot("AAA", "80", now - timedelta(seconds=5))})
    before_revision = portfolio.revision
    candle_count = await db_session.scalar(select(func.count()).select_from(DailyCandle))
    paper_count = await db_session.scalar(select(func.count()).select_from(PaperValidationRecord))

    brief = await LivePortfolioService(
        db_session, provider, cache=LiveMarketCache(), now=now
    ).refresh(portfolio.id)

    assert provider.requests == [["AAA"]]
    assert brief.requested_tickers == 1
    assert brief.successful_tickers == 1
    assert brief.overall_readiness == LiveBriefReadiness.LIVE
    item = brief.positions[0]
    assert item.live is not None
    assert item.live.quote_timestamp == now - timedelta(seconds=5)
    assert item.live.freshness == LiveQuoteFreshness.LIVE
    closes = [Decimal(100 + day) / Decimal("2") for day in range(160)]
    assert item.completed_ema20 == calculate_ema_series(closes, 20)[-1]
    assert item.provisional_ema20 == calculate_ema_series([*closes, Decimal("80")], 20)[-1]
    assert item.provisional_ema50 == calculate_ema_series([*closes, Decimal("80")], 50)[-1]
    assert item.completed_atr14 is not None
    assert item.provisional_atr14 is not None
    assert item.live_status == LiveMonitoringStatus.CRITICAL_ATTENTION
    assert item.projection_is_official is False
    assert item.confirmed_sell_required is False
    assert portfolio.revision == before_revision
    assert await db_session.scalar(select(func.count()).select_from(DailyCandle)) == candle_count
    assert (
        await db_session.scalar(select(func.count()).select_from(PaperValidationRecord))
        == paper_count
    )
    assert companies[0].ticker == "AAA"


@pytest.mark.asyncio
async def test_live_refresh_partial_and_stale_are_explicit(db_session) -> None:
    portfolio, _ = await _portfolio(db_session, second=True)
    now = datetime(2025, 6, 10, 15, 0, tzinfo=UTC)
    provider = FakeLiveProvider({"AAA": _snapshot("AAA", "140", now - timedelta(minutes=10))})
    brief = await LivePortfolioService(
        db_session, provider, cache=LiveMarketCache(), now=now
    ).refresh(portfolio.id)

    assert provider.requests == [["AAA", "BBB"]]
    assert brief.overall_readiness == LiveBriefReadiness.PARTIAL
    assert brief.positions[0].live is not None
    assert brief.positions[0].live.freshness == LiveQuoteFreshness.STALE
    assert brief.positions[0].live_status == LiveMonitoringStatus.UNAVAILABLE
    assert brief.positions[1].live is None
    assert brief.partial_failures == ("BBB: No live snapshot returned",)


@pytest.mark.asyncio
async def test_live_refresh_api_is_typed_end_to_end(client: AsyncClient, db_session) -> None:
    portfolio, _ = await _portfolio(db_session)
    now = datetime(2025, 6, 10, 15, 0, tzinfo=UTC)
    service = LivePortfolioService(
        db_session,
        FakeLiveProvider({"AAA": _snapshot("AAA", "80", now - timedelta(seconds=5))}),
        cache=LiveMarketCache(),
        now=now,
    )
    app.dependency_overrides[get_live_portfolio_service] = lambda: service
    try:
        response = await client.post(f"/api/v1/portfolio/{portfolio.id}/live-refresh")
    finally:
        app.dependency_overrides.pop(get_live_portfolio_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "fake-live"
    assert payload["requested_tickers"] == 1
    assert payload["positions"][0]["ticker"] == "AAA"
    assert payload["positions"][0]["projection_is_official"] is False
