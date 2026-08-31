from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.company import Company
from alphapilot.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(
            session,
            Company,
        )

    async def get_by_ticker(
        self,
        ticker: str,
    ) -> Company | None:
        result = await self.session.execute(
            select(Company).where(
                Company.ticker == ticker.upper(),
            )
        )

        return result.scalar_one_or_none()

    async def get_many(self, company_ids: list[UUID]) -> list[Company]:
        if not company_ids:
            return []
        result = await self.session.execute(
            select(Company).where(Company.id.in_(company_ids)).order_by(Company.ticker)
        )
        return list(result.scalars().all())

    async def update(
        self,
        company: Company,
    ) -> Company:
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(company)

        return company

    async def list_custom_tracked(self, *, active_only: bool = True) -> list[Company]:
        statement = select(Company).where(Company.is_custom_tracked.is_(True))
        if active_only:
            statement = statement.where(Company.is_active.is_(True))
        result = await self.session.execute(statement.order_by(Company.ticker))
        return list(result.scalars().all())
