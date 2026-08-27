from dataclasses import FrozenInstanceError, replace

import pytest

from alphapilot.api.routes.portfolio import strategy_profile_plan_id
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.schemas.portfolio import CurrentPortfolioSchema, PortfolioPlanRequest
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.profile import (
    ResearchClassification,
    list_strategy_profiles,
    resolve_strategy_profile,
    resolve_strategy_profile_identity,
)


def test_profiles_are_deterministic_and_exact() -> None:
    first = list_strategy_profiles()
    second = list_strategy_profiles()
    assert first is second
    assert [profile.profile_id for profile in first] == [
        "ema20-pullback-v1",
        "micho-150-v1",
    ]

    ema = resolve_strategy_profile(StrategyName.EMA20_PULLBACK)
    assert ema.classification == ResearchClassification.PROMISING_RESEARCH_BASELINE
    assert ema.sizing_policy == SizingPolicyName.EQUAL_SLOT
    assert str(ema.hybrid_trend_threshold_pct) == "2"
    assert ema.protective_stop_default == "NONE"
    assert ema.research_only_stop_candidate == "Static 3 × ATR14"

    micho = resolve_strategy_profile(StrategyName.MICHO_150)
    assert micho.sizing_policy == SizingPolicyName.ATR_VOLATILITY_NORMALIZED
    assert micho.micho_entry_mode == "both"
    assert micho.protective_stop_default == "NONE"
    assert micho.research_only_stop_candidate == "Static 1.5 × ATR14"


def test_profile_is_immutable_and_unknown_identity_fails() -> None:
    profile = resolve_strategy_profile(StrategyName.EMA20_PULLBACK)
    with pytest.raises(FrozenInstanceError):
        profile.version = 2  # type: ignore[misc]
    with pytest.raises(ValueError, match="Unknown strategy profile"):
        resolve_strategy_profile_identity("unknown-v1", 1)
    with pytest.raises(ValueError, match="version mismatch"):
        resolve_strategy_profile_identity(profile.profile_id, 2)


def test_profile_version_participates_in_plan_identity() -> None:
    request = PortfolioPlanRequest(
        strategy=StrategyName.EMA20_PULLBACK,
        portfolio=CurrentPortfolioSchema(cash=100_000),
    )
    profile = resolve_strategy_profile(StrategyName.EMA20_PULLBACK)
    assert strategy_profile_plan_id(request, profile) != strategy_profile_plan_id(
        request,
        replace(profile, version=2),
    )
