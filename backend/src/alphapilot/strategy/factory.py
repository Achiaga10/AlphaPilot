from decimal import Decimal

from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.ema20_pullback import (
    EMA20PullbackStrategy,
)
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho150 import Micho150Strategy
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName


def create_strategy(
    strategy_name: StrategyName,
    *,
    exit_mode: TrendExitMode = TrendExitMode.EMA50,
    hybrid_trend_threshold_pct: Decimal = Decimal("3"),
    micho_entry_mode: MichoEntryMode = MichoEntryMode.BOTH,
) -> TradingStrategy:
    if strategy_name == StrategyName.MICHO_150:
        return Micho150Strategy(
            entry_mode=micho_entry_mode,
        )

    return EMA20PullbackStrategy(
        exit_mode=exit_mode,
        hybrid_trend_threshold_pct=(hybrid_trend_threshold_pct),
    )


def get_strategy_stock_warmup_days(
    strategy_name: StrategyName,
) -> int:
    if strategy_name == StrategyName.MICHO_150:
        return 260

    return 120
