from alphapilot.database.models.company import Company
from alphapilot.market.providers.base import (
    IndexConstituentDetailsProvider,
)
from alphapilot.services.company import CompanyService


class UniverseCompanySyncService:
    """Creates companies from index constituent metadata."""

    def __init__(
        self,
        provider: IndexConstituentDetailsProvider,
        company_service: CompanyService,
    ) -> None:
        self.provider = provider
        self.company_service = company_service

    async def sync_companies(
        self,
        index_symbol: str,
    ) -> int:
        constituents = await self.provider.get_index_constituent_details(
            index_symbol,
        )

        if not constituents:
            raise RuntimeError(f"Provider returned no constituent details for {index_symbol}")

        created_count = 0

        for item in constituents:
            existing = await self.company_service.get_company(
                item.ticker,
            )

            if existing is not None:
                continue

            company = Company(
                ticker=item.ticker,
                name=item.name,
                exchange=item.exchange,
                sector=item.sector,
                industry=item.industry,
                is_active=True,
            )

            await self.company_service.create(
                company,
            )

            created_count += 1

        return created_count
