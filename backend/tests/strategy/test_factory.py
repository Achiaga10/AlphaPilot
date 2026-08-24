from alphapilot.strategy.ema20_pullback import (
    EMA20PullbackStrategy,
)
from alphapilot.strategy.factory import (
    create_strategy,
    get_strategy_stock_warmup_days,
)
from alphapilot.strategy.micho150 import Micho150Strategy
from alphapilot.strategy.name import StrategyName


def test_factory_creates_micho_strategy() -> None:
    strategy = create_strategy(StrategyName.MICHO_150)

    assert isinstance(
        strategy,
        Micho150Strategy,
    )


def test_factory_creates_ema20_strategy() -> None:
    strategy = create_strategy(StrategyName.EMA20_PULLBACK)

    assert isinstance(
        strategy,
        EMA20PullbackStrategy,
    )


def test_micho_receives_longer_warmup() -> None:
    assert get_strategy_stock_warmup_days(StrategyName.MICHO_150) == 260


def test_ema20_keeps_existing_warmup() -> None:
    assert get_strategy_stock_warmup_days(StrategyName.EMA20_PULLBACK) == 120
