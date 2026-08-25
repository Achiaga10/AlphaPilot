from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from alphapilot.strategy.evaluation import SignalReason


@dataclass(slots=True, frozen=True)
class MultiPortfolioConfig:
    """Configuration for one shared-cash, multi-stock portfolio."""

    initial_capital: Decimal = Decimal("100000")
    max_positions: int = 10
    commission_per_order: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than 0")

        if self.max_positions <= 0:
            raise ValueError("max_positions must be greater than 0")

        if self.commission_per_order < 0:
            raise ValueError("commission_per_order must not be negative")

        if not (Decimal("0") <= self.slippage_bps < Decimal("10000")):
            raise ValueError("slippage_bps must be between 0 and 10000")


@dataclass(slots=True, frozen=True)
class MultiPortfolioPosition:
    ticker: str
    entry_signal_day: date
    entry_day: date
    entry_price: Decimal
    shares: int
    entry_commission: Decimal
    entry_reason: SignalReason | None

    @property
    def cost_basis(self) -> Decimal:
        return Decimal(self.shares) * self.entry_price + self.entry_commission


@dataclass(slots=True, frozen=True)
class MultiPortfolioTrade:
    ticker: str
    entry_signal_day: date
    entry_day: date
    entry_price: Decimal
    exit_signal_day: date
    exit_day: date
    exit_price: Decimal
    shares: int
    entry_commission: Decimal
    exit_commission: Decimal
    entry_reason: SignalReason | None
    exit_reason: SignalReason | None

    @property
    def cost_basis(self) -> Decimal:
        return Decimal(self.shares) * self.entry_price + self.entry_commission

    @property
    def proceeds(self) -> Decimal:
        return Decimal(self.shares) * self.exit_price - self.exit_commission

    @property
    def pnl(self) -> Decimal:
        return self.proceeds - self.cost_basis

    @property
    def return_pct(self) -> Decimal:
        if self.cost_basis == 0:
            return Decimal("0")

        return self.pnl / self.cost_basis * Decimal("100")


@dataclass(slots=True, frozen=True)
class MultiPortfolioEquityPoint:
    trading_day: date
    cash: Decimal
    invested_value: Decimal
    equity: Decimal
    open_positions: int


@dataclass(slots=True, frozen=True)
class MultiPortfolioSimulationResult:
    initial_capital: Decimal
    final_equity: Decimal
    equity_curve: tuple[MultiPortfolioEquityPoint, ...]
    trades: tuple[MultiPortfolioTrade, ...]
    open_positions: tuple[MultiPortfolioPosition, ...]

    @property
    def total_return_pct(self) -> Decimal:
        return (self.final_equity - self.initial_capital) / self.initial_capital * Decimal("100")
