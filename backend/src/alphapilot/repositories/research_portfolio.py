from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import (
    ResearchPortfolio,
    ResearchPosition,
    ResearchPositionStatus,
    ResearchTradeEvent,
)


class ResearchPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_current(self, stable_key: str = "default") -> ResearchPortfolio | None:
        result = await self.session.execute(
            select(ResearchPortfolio).where(ResearchPortfolio.stable_key == stable_key)
        )
        return result.scalar_one_or_none()

    async def get(
        self, portfolio_id: UUID, *, for_update: bool = False
    ) -> ResearchPortfolio | None:
        statement = select(ResearchPortfolio).where(ResearchPortfolio.id == portfolio_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_open_positions(self, portfolio_id: UUID) -> list[ResearchPosition]:
        result = await self.session.execute(
            select(ResearchPosition)
            .where(
                ResearchPosition.portfolio_id == portfolio_id,
                ResearchPosition.status == ResearchPositionStatus.OPEN.value,
            )
            .order_by(ResearchPosition.ticker_at_entry)
        )
        return list(result.scalars().all())

    async def get_open_position(
        self, portfolio_id: UUID, company_id: UUID
    ) -> ResearchPosition | None:
        result = await self.session.execute(
            select(ResearchPosition).where(
                ResearchPosition.portfolio_id == portfolio_id,
                ResearchPosition.company_id == company_id,
                ResearchPosition.status == ResearchPositionStatus.OPEN.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_events(self, portfolio_id: UUID) -> list[ResearchTradeEvent]:
        result = await self.session.execute(
            select(ResearchTradeEvent)
            .where(ResearchTradeEvent.portfolio_id == portfolio_id)
            .order_by(ResearchTradeEvent.created_at, ResearchTradeEvent.id)
        )
        return list(result.scalars().all())

    def add(self, value: ResearchPortfolio | ResearchPosition | ResearchTradeEvent) -> None:
        self.session.add(value)

    async def flush(self) -> None:
        await self.session.flush()
