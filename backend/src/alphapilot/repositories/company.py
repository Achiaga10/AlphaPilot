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

    async def update(
        self,
        company: Company,
    ) -> Company:
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(company)

        return company
