from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.market.session import CompletedDailySessionPolicy
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.research_data import ResearchDataRepository


def policy_at(value: datetime) -> CompletedDailySessionPolicy:
    return CompletedDailySessionPolicy(now_provider=lambda: value)


def candle(company: Company, day: date, close: str) -> DailyCandle:
    value = Decimal(close)
    return DailyCandle(
        company_id=company.id,
        trading_day=day,
        open=value,
        high=value + 1,
        low=value - 1,
        close=value,
        volume=100,
    )


@pytest.mark.asyncio
async def test_repository_quarantines_legacy_partial_and_later_upsert_replaces_it(
    db_session: AsyncSession,
) -> None:
    company = Company(ticker="DONE", name="Completed", exchange="NYSE", is_active=True)
    db_session.add(company)
    await db_session.flush()
    db_session.add_all(
        [
            candle(company, date(2026, 8, 25), "100"),
            candle(company, date(2026, 8, 26), "101"),  # legacy/in-progress row
        ]
    )
    await db_session.commit()

    open_session = DailyCandleRepository(
        db_session, policy_at(datetime(2026, 8, 26, 18, 0, tzinfo=UTC))
    )
    history = await open_session.get_history(company.id, date(2026, 8, 1), date(2026, 8, 26))
    latest = await open_session.get_latest(company.id)
    assert [item.trading_day for item in history] == [date(2026, 8, 25)]
    assert latest is not None and latest.trading_day == date(2026, 8, 25)

    completed_session = DailyCandleRepository(
        db_session, policy_at(datetime(2026, 8, 26, 20, 16, tzinfo=UTC))
    )
    await completed_session.upsert_many([candle(company, date(2026, 8, 26), "105")])
    latest = await completed_session.get_latest(company.id)
    assert latest is not None
    assert latest.trading_day == date(2026, 8, 26)
    assert latest.close == Decimal("105")


@pytest.mark.asyncio
async def test_repository_refuses_to_persist_incomplete_daily_bar(
    db_session: AsyncSession,
) -> None:
    company = Company(ticker="OPEN", name="Open", exchange="NYSE", is_active=True)
    db_session.add(company)
    await db_session.flush()
    repository = DailyCandleRepository(
        db_session, policy_at(datetime(2026, 8, 26, 18, 0, tzinfo=UTC))
    )

    await repository.upsert_many([candle(company, date(2026, 8, 26), "101")])

    assert await repository.get_latest(company.id) is None


@pytest.mark.asyncio
async def test_admin_freshness_queries_report_only_completed_sessions(
    db_session: AsyncSession,
) -> None:
    spy = Company(
        ticker="SPY",
        name="SPY",
        exchange="NYSE",
        is_active=True,
        is_custom_tracked=True,
    )
    db_session.add(spy)
    await db_session.flush()
    db_session.add_all(
        [
            candle(spy, date(2026, 8, 25), "765"),
            candle(spy, date(2026, 8, 26), "999"),
        ]
    )
    await db_session.commit()
    repository = ResearchDataRepository(
        db_session, policy_at(datetime(2026, 8, 26, 18, 0, tzinfo=UTC))
    )

    assert await repository.latest_candle_date("SPY") == date(2026, 8, 25)
    count, first, latest = await repository.company_candle_summary("SPY")
    assert (count, first, latest) == (1, date(2026, 8, 25), date(2026, 8, 25))
    assert await repository.active_tracked_latest_date_range("^GSPC") == (
        date(2026, 8, 25),
        date(2026, 8, 25),
    )
