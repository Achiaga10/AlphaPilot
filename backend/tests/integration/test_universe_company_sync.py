import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.market.dto import IndexConstituentData
from alphapilot.market.providers.base import (
    IndexConstituentDetailsProvider,
)
from alphapilot.repositories.company import (
    CompanyRepository,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.universe_company_sync import (
    UniverseCompanySyncService,
)


class FakeDetailsProvider(
    IndexConstituentDetailsProvider,
):
    async def get_index_constituent_details(
        self,
        index_symbol: str,
    ) -> list[IndexConstituentData]:
        return [
            IndexConstituentData(
                ticker="AAPL",
                name="Apple Inc.",
                exchange="NASDAQ",
                sector="Information Technology",
                industry=("Technology Hardware, Storage & Peripherals"),
            ),
            IndexConstituentData(
                ticker="NVDA",
                name="Nvidia",
                exchange="NASDAQ",
                sector="Information Technology",
                industry="Semiconductors",
            ),
        ]


@pytest.mark.asyncio
async def test_universe_company_sync_creates_missing_companies(
    db_session: AsyncSession,
) -> None:
    company_service = CompanyService(
        CompanyRepository(db_session),
    )

    service = UniverseCompanySyncService(
        provider=FakeDetailsProvider(),
        company_service=company_service,
    )

    created = await service.sync_companies(
        "^GSPC",
    )

    assert created == 2

    apple = await company_service.get_company(
        "AAPL",
    )

    assert apple is not None
    assert apple.name == "Apple Inc."
    assert apple.exchange == "NASDAQ"
    assert apple.sector == "Information Technology"

    second_run = await service.sync_companies(
        "^GSPC",
    )

    assert second_run == 0
