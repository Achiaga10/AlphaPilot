from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from alphapilot.strategy.evaluation import StrategyEvaluation
from alphapilot.strategy.signal import Signal


@dataclass(slots=True, frozen=True)
class BacktestBarResult:
    """Strategy evaluation for one historical trading day."""

    trading_day: date
    open: Decimal
    close: Decimal
    evaluation: StrategyEvaluation

    @property
    def signal(self) -> Signal:
        return self.evaluation.signal


@dataclass(slots=True, frozen=True)
class BacktestResult:
    """Historical strategy evaluations for one company."""

    ticker: str
    start: date | None
    end: date | None
    bars: tuple[BacktestBarResult, ...]

    @property
    def total_bars(self) -> int:
        return len(self.bars)


@dataclass(slots=True, frozen=True)
class BacktestPosition:
    """Open position created by a historical BUY signal."""

    entry_signal_day: date
    entry_day: date
    entry_price: Decimal


@dataclass(slots=True, frozen=True)
class BacktestTrade:
    """Completed historical long trade."""

    entry_signal_day: date
    entry_day: date
    entry_price: Decimal

    exit_signal_day: date
    exit_day: date
    exit_price: Decimal

    @property
    def return_pct(self) -> Decimal:
        if self.entry_price == 0:
            return Decimal("0")

        return (self.exit_price - self.entry_price) / self.entry_price * Decimal("100")


@dataclass(slots=True, frozen=True)
class TradeSimulationResult:
    """Result of converting historical signals into trades."""

    ticker: str
    trades: tuple[BacktestTrade, ...]
    open_position: BacktestPosition | None

    @property
    def total_trades(self) -> int:
        return len(self.trades)


@dataclass(slots=True, frozen=True)
class PortfolioConfig:
    """Configuration for a single-asset portfolio simulation."""

    initial_capital: Decimal = Decimal("100000")
    position_size_pct: Decimal = Decimal("100")
    commission_per_order: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than 0")

        if not (Decimal("0") < self.position_size_pct <= Decimal("100")):
            raise ValueError("position_size_pct must be between 0 and 100")

        if self.commission_per_order < 0:
            raise ValueError("commission_per_order must not be negative")

        if not (Decimal("0") <= self.slippage_bps < Decimal("10000")):
            raise ValueError("slippage_bps must be between 0 and 10000")


@dataclass(slots=True, frozen=True)
class PortfolioPosition:
    """An open position held by the simulated portfolio."""

    entry_signal_day: date
    entry_day: date
    entry_price: Decimal
    shares: int
    entry_commission: Decimal

    @property
    def cost_basis(self) -> Decimal:
        return Decimal(self.shares) * self.entry_price + self.entry_commission


@dataclass(slots=True, frozen=True)
class PortfolioTrade:
    """A completed portfolio trade."""

    entry_signal_day: date
    entry_day: date
    entry_price: Decimal

    exit_signal_day: date
    exit_day: date
    exit_price: Decimal

    shares: int

    entry_commission: Decimal
    exit_commission: Decimal

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
class EquityCurvePoint:
    """Portfolio value at the close of one trading day."""

    trading_day: date
    cash: Decimal
    shares: int
    market_price: Decimal
    equity: Decimal


@dataclass(slots=True, frozen=True)
class PortfolioSimulationResult:
    """Result of a single-asset portfolio simulation."""

    ticker: str
    initial_capital: Decimal
    final_equity: Decimal

    equity_curve: tuple[EquityCurvePoint, ...]

    trades: tuple[PortfolioTrade, ...]

    open_position: PortfolioPosition | None

    @property
    def total_return_pct(self) -> Decimal:
        if self.initial_capital == 0:
            return Decimal("0")

        return (self.final_equity - self.initial_capital) / self.initial_capital * Decimal("100")
