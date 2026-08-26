from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.index_constituent import (
    IndexConstituent,
)
from alphapilot.repositories.base import BaseRepository


class IndexConstituentRepository(
    BaseRepository[IndexConstituent],
):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(
            session,
            IndexConstituent,
        )

    async def list_for_index(
        self,
        index_symbol: str,
    ) -> list[IndexConstituent]:
        result = await self.session.execute(
            select(IndexConstituent)
            .where(
                IndexConstituent.index_symbol == index_symbol.upper(),
            )
            .order_by(IndexConstituent.ticker)
        )

        return list(result.scalars().all())

    async def list_active(
        self,
        index_symbol: str,
    ) -> list[IndexConstituent]:
        result = await self.session.execute(
            select(IndexConstituent)
            .where(
                IndexConstituent.index_symbol == index_symbol.upper(),
                IndexConstituent.is_active.is_(True),
            )
            .order_by(IndexConstituent.ticker)
        )

        return list(result.scalars().all())

    async def sync_current(
        self,
        index_symbol: str,
        tickers: list[str],
    ) -> list[IndexConstituent]:
        normalized_index_symbol = index_symbol.strip().upper()

        normalized_tickers = {ticker.strip().upper() for ticker in tickers if ticker.strip()}

        existing = await self.list_for_index(
            normalized_index_symbol,
        )

        existing_by_ticker = {constituent.ticker: constituent for constituent in existing}

        for constituent in existing:
            constituent.is_active = constituent.ticker in normalized_tickers

        for ticker in normalized_tickers:
            if ticker in existing_by_ticker:
                continue

            self.session.add(
                IndexConstituent(
                    index_symbol=normalized_index_symbol,
                    ticker=ticker,
                    is_active=True,
                )
            )

        await self.session.commit()

        return await self.list_active(
            normalized_index_symbol,
        )

    async def is_active_member(self, index_symbol: str, ticker: str) -> bool:
        result = await self.session.execute(
            select(IndexConstituent.id).where(
                IndexConstituent.index_symbol == index_symbol.strip().upper(),
                IndexConstituent.ticker == ticker.strip().upper(),
                IndexConstituent.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None
