from uuid import UUID

from alphapilot.database.models.company import Company
from alphapilot.repositories.company import CompanyRepository
from alphapilot.schemas.company import CompanyUpdate
from alphapilot.services.base import BaseService


class CompanyService(BaseService[CompanyRepository]):
    def __init__(
        self,
        repository: CompanyRepository,
    ) -> None:
        super().__init__(repository)

    async def create(
        self,
        company: Company,
    ) -> Company:
        return await self.repository.create(company)

    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        return await self.repository.get_by_ticker(ticker)

    async def list_companies(
        self,
    ) -> list[Company]:
        return await self.repository.list()

    async def list_custom_tracked(self, *, active_only: bool = True) -> list[Company]:
        return await self.repository.list_custom_tracked(active_only=active_only)

    async def update_company(
        self,
        company_id: UUID,
        data: CompanyUpdate,
    ) -> Company | None:
        company = await self.repository.get(company_id)

        if company is None:
            return None

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(company, field, value)

        return await self.repository.update(company)

    async def delete_company(
        self,
        company_id: UUID,
    ) -> bool:
        company = await self.repository.get(company_id)

        if company is None:
            return False

        await self.repository.delete(company)

        return True
