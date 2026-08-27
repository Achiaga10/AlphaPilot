from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from alphapilot.backtesting.candidate_selection import SelectionPolicyName
from alphapilot.portfolio.sizing import SizingPolicyName
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.name import StrategyName


class ResearchClassification(StrEnum):
    PROMISING_RESEARCH_BASELINE = "PROMISING_RESEARCH_BASELINE"
    RESEARCH_ONLY = "RESEARCH_ONLY"


class TradeManagementDefault(StrEnum):
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    profile_id: str
    version: int
    strategy: StrategyName
    display_name: str
    classification: ResearchClassification
    entry_description: str
    recommended_selection_policy: SelectionPolicyName
    allowed_selection_policies: tuple[SelectionPolicyName, ...]
    sizing_policy: SizingPolicyName
    strategy_exit_description: str
    ema_exit_mode: TrendExitMode | None
    hybrid_trend_threshold_pct: Decimal | None
    micho_entry_mode: MichoEntryMode | None
    protective_stop_default: TradeManagementDefault
    profit_management_default: TradeManagementDefault
    research_only_stop_candidate: str


EMA20_PULLBACK_V1 = StrategyProfile(
    profile_id="ema20-pullback-v1",
    version=1,
    strategy=StrategyName.EMA20_PULLBACK,
    display_name="EMA20 Pullback",
    classification=ResearchClassification.PROMISING_RESEARCH_BASELINE,
    entry_description="Existing EMA20 Pullback reclaim entry",
    recommended_selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
    allowed_selection_policies=(
        SelectionPolicyName.RELATIVE_STRENGTH_20,
        SelectionPolicyName.TICKER_ASCENDING,
    ),
    sizing_policy=SizingPolicyName.EQUAL_SLOT,
    strategy_exit_description="HYBRID exit with frozen 2% threshold",
    ema_exit_mode=TrendExitMode.HYBRID,
    hybrid_trend_threshold_pct=Decimal("2"),
    micho_entry_mode=None,
    protective_stop_default=TradeManagementDefault.NONE,
    profit_management_default=TradeManagementDefault.NONE,
    research_only_stop_candidate="Static 3 × ATR14",
)

MICHO_150_V1 = StrategyProfile(
    profile_id="micho-150-v1",
    version=1,
    strategy=StrategyName.MICHO_150,
    display_name="Micho 150",
    classification=ResearchClassification.PROMISING_RESEARCH_BASELINE,
    entry_description="Micho V1 BOTH entry mode",
    recommended_selection_policy=SelectionPolicyName.RELATIVE_STRENGTH_20,
    allowed_selection_policies=(
        SelectionPolicyName.RELATIVE_STRENGTH_20,
        SelectionPolicyName.TICKER_ASCENDING,
    ),
    sizing_policy=SizingPolicyName.ATR_VOLATILITY_NORMALIZED,
    strategy_exit_description="Close below SMA150",
    ema_exit_mode=None,
    hybrid_trend_threshold_pct=None,
    micho_entry_mode=MichoEntryMode.BOTH,
    protective_stop_default=TradeManagementDefault.NONE,
    profit_management_default=TradeManagementDefault.NONE,
    research_only_stop_candidate="Static 1.5 × ATR14",
)

STRATEGY_PROFILES = (EMA20_PULLBACK_V1, MICHO_150_V1)
_BY_STRATEGY = MappingProxyType({profile.strategy: profile for profile in STRATEGY_PROFILES})
_BY_ID = MappingProxyType({profile.profile_id: profile for profile in STRATEGY_PROFILES})


def list_strategy_profiles() -> tuple[StrategyProfile, ...]:
    return STRATEGY_PROFILES


def resolve_strategy_profile(strategy: StrategyName) -> StrategyProfile:
    try:
        return _BY_STRATEGY[strategy]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy profile for {strategy}") from exc


def resolve_strategy_profile_identity(profile_id: str, version: int) -> StrategyProfile:
    try:
        profile = _BY_ID[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy profile: {profile_id}") from exc
    if profile.version != version:
        raise ValueError(
            f"Strategy profile version mismatch for {profile_id}: expected {profile.version}"
        )
    return profile
