from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.index_constituent import IndexConstituent
from alphapilot.market.session import CompletedDailySessionPolicy


class ResearchDataRepository:
    """Read-only aggregate queries for the research-admin freshness view."""

    def __init__(
        self,
        session: AsyncSession,
        session_policy: CompletedDailySessionPolicy | None = None,
    ) -> None:
        self.session = session
        self.session_policy = session_policy or CompletedDailySessionPolicy()

    async def count_active_companies(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Company).where(Company.is_active.is_(True))
        )
        return int(result.scalar_one())

    async def count_active_constituents(self, index_symbol: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(IndexConstituent)
            .where(
                IndexConstituent.index_symbol == index_symbol.upper(),
                IndexConstituent.is_active.is_(True),
            )
        )
        return int(result.scalar_one())

    async def count_active_custom_tracked(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Company)
            .where(
                Company.is_active.is_(True),
                Company.is_custom_tracked.is_(True),
            )
        )
        return int(result.scalar_one())

    async def list_market_sync_targets(self, index_symbol: str) -> list[str]:
        constituent_rows = await self.session.execute(
            select(IndexConstituent.ticker).where(
                IndexConstituent.index_symbol == index_symbol.upper(),
                IndexConstituent.is_active.is_(True),
            )
        )
        custom_rows = await self.session.execute(
            select(Company.ticker).where(
                Company.is_active.is_(True),
                Company.is_custom_tracked.is_(True),
            )
        )
        return sorted(set(constituent_rows.scalars().all()) | set(custom_rows.scalars().all()))

    async def company_candle_summary(self, ticker: str) -> tuple[int, date | None, date | None]:
        result = await self.session.execute(
            select(
                func.count(DailyCandle.id),
                func.min(DailyCandle.trading_day),
                func.max(DailyCandle.trading_day),
            )
            .join(Company, Company.id == DailyCandle.company_id)
            .where(
                Company.ticker == ticker.upper(),
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
        )
        row = result.one()
        return int(row[0]), row[1], row[2]

    async def latest_candle_date(self, ticker: str) -> date | None:
        result = await self.session.execute(
            select(func.max(DailyCandle.trading_day))
            .join(Company, Company.id == DailyCandle.company_id)
            .where(
                Company.ticker == ticker.upper(),
                DailyCandle.trading_day <= self.session_policy.completed_through(),
            )
        )
        return result.scalar_one()

    async def active_tracked_latest_date_range(
        self, index_symbol: str
    ) -> tuple[date | None, date | None]:
        latest_by_ticker = self._active_tracked_latest_dates(
            index_symbol, self.session_policy.completed_through()
        )
        result = await self.session.execute(
            select(
                func.min(latest_by_ticker.c.latest_day),
                func.max(latest_by_ticker.c.latest_day),
            )
        )
        row = result.one()
        return row[0], row[1]

    async def count_stale_tracked_tickers(
        self, index_symbol: str, benchmark_date: date | None
    ) -> int:
        if benchmark_date is None:
            return 0
        latest_by_ticker = self._active_tracked_latest_dates(
            index_symbol, self.session_policy.completed_through()
        )
        result = await self.session.execute(
            select(func.count())
            .select_from(latest_by_ticker)
            .where(latest_by_ticker.c.latest_day < benchmark_date)
        )
        return int(result.scalar_one())

    async def count_fresh_tracked_tickers(
        self, index_symbol: str, benchmark_date: date | None
    ) -> int:
        if benchmark_date is None:
            return 0
        latest_by_ticker = self._active_tracked_latest_dates(
            index_symbol, self.session_policy.completed_through()
        )
        result = await self.session.execute(
            select(func.count())
            .select_from(latest_by_ticker)
            .where(latest_by_ticker.c.latest_day == benchmark_date)
        )
        return int(result.scalar_one())

    async def count_no_data_tracked_tickers(self, index_symbol: str) -> int:
        latest_by_ticker = self._active_tracked_latest_dates(
            index_symbol, self.session_policy.completed_through()
        )
        result = await self.session.execute(
            select(func.count())
            .select_from(latest_by_ticker)
            .where(latest_by_ticker.c.latest_day.is_(None))
        )
        return int(result.scalar_one())

    @staticmethod
    def _active_tracked_latest_dates(index_symbol: str, completed_through: date) -> Subquery:
        return (
            select(func.max(DailyCandle.trading_day).label("latest_day"))
            .select_from(Company)
            .outerjoin(
                IndexConstituent,
                and_(
                    IndexConstituent.ticker == Company.ticker,
                    IndexConstituent.index_symbol == index_symbol.upper(),
                    IndexConstituent.is_active.is_(True),
                ),
            )
            .outerjoin(
                DailyCandle,
                and_(
                    DailyCandle.company_id == Company.id,
                    DailyCandle.trading_day <= completed_through,
                ),
            )
            .where(
                Company.is_active.is_(True),
                or_(
                    Company.is_custom_tracked.is_(True),
                    IndexConstituent.ticker.is_not(None),
                ),
            )
            .group_by(Company.id)
            .subquery()
        )
