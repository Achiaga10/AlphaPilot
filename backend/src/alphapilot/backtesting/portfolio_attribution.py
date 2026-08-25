from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioSimulationResult


@dataclass(slots=True, frozen=True)
class TickerAttribution:
    ticker: str
    sector: str
    completed_trades: int
    open_positions: int
    gross_realized_pnl: Decimal
    gross_unrealized_pnl: Decimal
    transaction_friction: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    contribution_pct: Decimal | None


@dataclass(slots=True, frozen=True)
class SectorAttribution:
    sector: str
    unique_tickers: int
    completed_trades: int
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    contribution_pct: Decimal | None


@dataclass(slots=True, frozen=True)
class AttributionSummary:
    tickers: tuple[TickerAttribution, ...]
    sectors: tuple[SectorAttribution, ...]
    gross_realized_pnl: Decimal
    gross_unrealized_pnl: Decimal
    transaction_friction: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    reconciliation_residual: Decimal
    unique_tickers_held: int
    positive_tickers: int
    negative_tickers: int
    top_1_pnl: Decimal
    top_5_pnl: Decimal
    top_10_pnl: Decimal
    top_1_gain_share_pct: Decimal | None
    top_5_gain_share_pct: Decimal | None
    top_10_gain_share_pct: Decimal | None
    top_1_positive_pnl_share_pct: Decimal | None
    top_5_positive_pnl_share_pct: Decimal | None
    positive_pnl_hhi: Decimal | None


class PortfolioAttributionCalculator:
    UNKNOWN_SECTOR = "Unknown"

    def calculate(self, portfolio: MultiPortfolioSimulationResult) -> AttributionSummary:
        final_prices = dict(portfolio.final_prices)
        values: dict[str, dict[str, Decimal | int | str]] = defaultdict(
            lambda: {
                "sector": self.UNKNOWN_SECTOR,
                "completed": 0,
                "open": 0,
                "gross_realized": Decimal("0"),
                "gross_unrealized": Decimal("0"),
                "friction_realized": Decimal("0"),
                "friction_unrealized": Decimal("0"),
            }
        )

        for trade in portfolio.trades:
            item = values[trade.ticker]
            item["sector"] = trade.sector or self.UNKNOWN_SECTOR
            item["completed"] = int(item["completed"]) + 1
            shares = Decimal(trade.shares)
            item["gross_realized"] = Decimal(item["gross_realized"]) + shares * (
                trade.exit_reference_price - trade.entry_reference_price
            )
            item["friction_realized"] = Decimal(item["friction_realized"]) + (
                shares * (trade.entry_price - trade.entry_reference_price)
                + shares * (trade.exit_reference_price - trade.exit_price)
                + trade.entry_commission
                + trade.exit_commission
            )

        for position in portfolio.open_positions:
            item = values[position.ticker]
            item["sector"] = position.sector or self.UNKNOWN_SECTOR
            item["open"] = int(item["open"]) + 1
            shares = Decimal(position.shares)
            item["gross_unrealized"] = Decimal(item["gross_unrealized"]) + shares * (
                final_prices[position.ticker] - position.entry_reference_price
            )
            item["friction_unrealized"] = Decimal(item["friction_unrealized"]) + (
                shares * (position.entry_price - position.entry_reference_price)
                + position.entry_commission
            )

        total_pnl = portfolio.final_equity - portfolio.initial_capital
        rows: list[TickerAttribution] = []
        for ticker, item in values.items():
            gross_realized = Decimal(item["gross_realized"])
            gross_unrealized = Decimal(item["gross_unrealized"])
            realized = gross_realized - Decimal(item["friction_realized"])
            unrealized = gross_unrealized - Decimal(item["friction_unrealized"])
            combined = realized + unrealized
            rows.append(
                TickerAttribution(
                    ticker=ticker,
                    sector=str(item["sector"]),
                    completed_trades=int(item["completed"]),
                    open_positions=int(item["open"]),
                    gross_realized_pnl=gross_realized,
                    gross_unrealized_pnl=gross_unrealized,
                    transaction_friction=(
                        Decimal(item["friction_realized"]) + Decimal(item["friction_unrealized"])
                    ),
                    realized_pnl=realized,
                    unrealized_pnl=unrealized,
                    total_pnl=combined,
                    contribution_pct=(
                        combined / total_pnl * Decimal("100") if total_pnl != 0 else None
                    ),
                )
            )
        ordered = tuple(sorted(rows, key=lambda row: (-row.total_pnl, row.ticker)))
        gross_realized_total = sum((row.gross_realized_pnl for row in ordered), Decimal("0"))
        gross_unrealized_total = sum((row.gross_unrealized_pnl for row in ordered), Decimal("0"))
        friction_total = sum((row.transaction_friction for row in ordered), Decimal("0"))
        realized_total = sum((row.realized_pnl for row in ordered), Decimal("0"))
        unrealized_total = sum((row.unrealized_pnl for row in ordered), Decimal("0"))
        positive = [row.total_pnl for row in ordered if row.total_pnl > 0]
        positive_total = sum(positive, Decimal("0"))

        return AttributionSummary(
            tickers=ordered,
            sectors=self._sectors(ordered, total_pnl),
            gross_realized_pnl=gross_realized_total,
            gross_unrealized_pnl=gross_unrealized_total,
            transaction_friction=friction_total,
            realized_pnl=realized_total,
            unrealized_pnl=unrealized_total,
            total_pnl=realized_total + unrealized_total,
            reconciliation_residual=(
                portfolio.final_equity
                - (
                    portfolio.initial_capital
                    + gross_realized_total
                    + gross_unrealized_total
                    - friction_total
                )
            ),
            unique_tickers_held=len(ordered),
            positive_tickers=len(positive),
            negative_tickers=sum(row.total_pnl < 0 for row in ordered),
            top_1_pnl=self._top_sum(ordered, 1),
            top_5_pnl=self._top_sum(ordered, 5),
            top_10_pnl=self._top_sum(ordered, 10),
            top_1_gain_share_pct=self._share(self._top_sum(ordered, 1), total_pnl),
            top_5_gain_share_pct=self._share(self._top_sum(ordered, 5), total_pnl),
            top_10_gain_share_pct=self._share(self._top_sum(ordered, 10), total_pnl),
            top_1_positive_pnl_share_pct=self._share(
                sum(positive[:1], Decimal("0")), positive_total
            ),
            top_5_positive_pnl_share_pct=self._share(
                sum(positive[:5], Decimal("0")), positive_total
            ),
            positive_pnl_hhi=(
                sum(
                    ((value / positive_total) ** 2 for value in positive),
                    Decimal("0"),
                )
                if positive_total > 0
                else None
            ),
        )

    @staticmethod
    def _top_sum(rows: tuple[TickerAttribution, ...], count: int) -> Decimal:
        return sum((row.total_pnl for row in rows[:count]), Decimal("0"))

    @staticmethod
    def _share(value: Decimal, total: Decimal) -> Decimal | None:
        return value / total * Decimal("100") if total != 0 else None

    def _sectors(
        self, rows: tuple[TickerAttribution, ...], total_pnl: Decimal
    ) -> tuple[SectorAttribution, ...]:
        grouped: dict[str, list[TickerAttribution]] = defaultdict(list)
        for row in rows:
            grouped[row.sector].append(row)
        result = []
        for sector, members in grouped.items():
            realized = sum((row.realized_pnl for row in members), Decimal("0"))
            unrealized = sum((row.unrealized_pnl for row in members), Decimal("0"))
            combined = realized + unrealized
            result.append(
                SectorAttribution(
                    sector=sector,
                    unique_tickers=len(members),
                    completed_trades=sum(row.completed_trades for row in members),
                    realized_pnl=realized,
                    unrealized_pnl=unrealized,
                    total_pnl=combined,
                    contribution_pct=self._share(combined, total_pnl),
                )
            )
        return tuple(sorted(result, key=lambda row: (-row.total_pnl, row.sector)))
