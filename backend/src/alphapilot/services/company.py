from alphapilot.database.models.company import Company
from alphapilot.repositories.company import CompanyRepository
from alphapilot.services.base import BaseService


class CompanyService(BaseService[CompanyRepository]):
    def __init__(
        self,
        repository: CompanyRepository,
    ) -> None:
        super().__init__(repository)

    async def get_company(
        self,
        ticker: str,
    ) -> Company | None:
        return await self.repository.get_by_ticker(ticker)

    async def list_companies(
        self,
    ) -> list[Company]:
        return await self.repository.list()
