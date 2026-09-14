from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.forward_portfolio import (
    ForwardCycle,
    ForwardEquityPoint,
    ForwardEvent,
    ForwardOrder,
    ForwardOrderSide,
    ForwardOrderStatus,
    ForwardPortfolio,
    ForwardPortfolioStatus,
    ForwardPosition,
    ForwardPositionStatus,
    ForwardTrade,
)
from alphapilot.database.models.research_portfolio import (
    PortfolioRecommendationStatus,
    PortfolioTickerPreference,
    ResearchPortfolio,
)


class ForwardPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def advisory_lock(self, portfolio_id: UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(2525, hashtext(:portfolio_key))"),
            {"portfolio_key": str(portfolio_id)},
        )

    async def get_current(self, *, for_update: bool = False) -> ForwardPortfolio | None:
        statement = (
            select(ForwardPortfolio)
            .where(
                ForwardPortfolio.strategy_id == "micho-150-v1",
                ForwardPortfolio.status.in_(
                    [ForwardPortfolioStatus.ACTIVE.value, ForwardPortfolioStatus.PAUSED.value]
                ),
            )
            .order_by(ForwardPortfolio.created_at.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get(self, portfolio_id: UUID, *, for_update: bool = False) -> ForwardPortfolio | None:
        statement = select(ForwardPortfolio).where(ForwardPortfolio.id == portfolio_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def completed_sessions(
        self, *, start: date, end: date, after: date | None = None
    ) -> list[date]:
        statement = (
            select(DailyCandle.trading_day)
            .join(Company, Company.id == DailyCandle.company_id)
            .where(
                Company.ticker == "SPY",
                DailyCandle.trading_day >= start,
                DailyCandle.trading_day <= end,
            )
            .order_by(DailyCandle.trading_day)
        )
        if after is not None:
            statement = statement.where(DailyCandle.trading_day > after)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def latest_completed_session(self, completed_through: date) -> date | None:
        result = await self.session.execute(
            select(func.max(DailyCandle.trading_day))
            .join(Company, Company.id == DailyCandle.company_id)
            .where(Company.ticker == "SPY", DailyCandle.trading_day <= completed_through)
        )
        return result.scalar_one_or_none()

    async def cycle(self, portfolio_id: UUID, trading_session: date) -> ForwardCycle | None:
        result = await self.session.execute(
            select(ForwardCycle).where(
                ForwardCycle.portfolio_id == portfolio_id,
                ForwardCycle.trading_session == trading_session,
            )
        )
        return result.scalar_one_or_none()

    async def latest_cycle(self, portfolio_id: UUID) -> ForwardCycle | None:
        result = await self.session.execute(
            select(ForwardCycle)
            .where(ForwardCycle.portfolio_id == portfolio_id)
            .order_by(ForwardCycle.trading_session.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def open_positions(self, portfolio_id: UUID) -> list[ForwardPosition]:
        result = await self.session.execute(
            select(ForwardPosition)
            .where(
                ForwardPosition.portfolio_id == portfolio_id,
                ForwardPosition.status == ForwardPositionStatus.OPEN.value,
            )
            .order_by(ForwardPosition.ticker)
        )
        return list(result.scalars().all())

    async def positions(self, portfolio_id: UUID) -> list[ForwardPosition]:
        result = await self.session.execute(
            select(ForwardPosition)
            .where(ForwardPosition.portfolio_id == portfolio_id)
            .order_by(ForwardPosition.created_at.desc())
        )
        return list(result.scalars().all())

    async def pending_orders(
        self, portfolio_id: UUID, *, side: ForwardOrderSide | None = None
    ) -> list[ForwardOrder]:
        statement = select(ForwardOrder).where(
            ForwardOrder.portfolio_id == portfolio_id,
            ForwardOrder.status == ForwardOrderStatus.PENDING.value,
        )
        if side is not None:
            statement = statement.where(ForwardOrder.side == side.value)
        result = await self.session.execute(
            statement.order_by(ForwardOrder.source_signal_session, ForwardOrder.ticker)
        )
        return list(result.scalars().all())

    async def orders(self, portfolio_id: UUID) -> list[ForwardOrder]:
        result = await self.session.execute(
            select(ForwardOrder)
            .where(ForwardOrder.portfolio_id == portfolio_id)
            .order_by(ForwardOrder.created_at.desc())
        )
        return list(result.scalars().all())

    async def trades(self, portfolio_id: UUID) -> list[ForwardTrade]:
        result = await self.session.execute(
            select(ForwardTrade)
            .where(ForwardTrade.portfolio_id == portfolio_id)
            .order_by(ForwardTrade.exit_session.desc(), ForwardTrade.ticker)
        )
        return list(result.scalars().all())

    async def events(self, portfolio_id: UUID, *, limit: int = 200) -> list[ForwardEvent]:
        result = await self.session.execute(
            select(ForwardEvent)
            .where(ForwardEvent.portfolio_id == portfolio_id)
            .order_by(ForwardEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def event_by_key(self, portfolio_id: UUID, key: str) -> ForwardEvent | None:
        result = await self.session.execute(
            select(ForwardEvent).where(
                ForwardEvent.portfolio_id == portfolio_id,
                ForwardEvent.idempotency_key == key,
            )
        )
        return result.scalar_one_or_none()

    async def equity_points(self, portfolio_id: UUID) -> list[ForwardEquityPoint]:
        result = await self.session.execute(
            select(ForwardEquityPoint)
            .where(ForwardEquityPoint.portfolio_id == portfolio_id)
            .order_by(ForwardEquityPoint.trading_session)
        )
        return list(result.scalars().all())

    async def company(self, ticker: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.ticker == ticker.upper()))
        return result.scalar_one_or_none()

    async def companies(self, company_ids: list[UUID]) -> dict[UUID, Company]:
        if not company_ids:
            return {}
        result = await self.session.execute(select(Company).where(Company.id.in_(company_ids)))
        return {item.id: item for item in result.scalars().all()}

    async def candle(self, company_id: UUID, trading_session: date) -> DailyCandle | None:
        result = await self.session.execute(
            select(DailyCandle).where(
                DailyCandle.company_id == company_id,
                DailyCandle.trading_day == trading_session,
            )
        )
        return result.scalar_one_or_none()

    async def excluded_tickers(self) -> frozenset[str]:
        result = await self.session.execute(
            select(PortfolioTickerPreference.ticker)
            .join(
                ResearchPortfolio,
                ResearchPortfolio.id == PortfolioTickerPreference.portfolio_id,
            )
            .where(
                ResearchPortfolio.stable_key == "default",
                PortfolioTickerPreference.recommendation_status
                == PortfolioRecommendationStatus.USER_EXCLUDED.value,
            )
        )
        return frozenset(ticker.upper() for ticker in result.scalars().all())

    def add(self, item: object) -> None:
        self.session.add(item)

    async def flush(self) -> None:
        await self.session.flush()
