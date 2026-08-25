from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class CostScenarioName(StrEnum):
    COST_0 = "cost-0"
    COST_LOW = "cost-low"
    COST_CONSERVATIVE = "cost-conservative"


@dataclass(slots=True, frozen=True)
class CostScenario:
    name: CostScenarioName
    commission_per_order: Decimal
    slippage_bps: Decimal


SCENARIOS = {
    CostScenarioName.COST_0: CostScenario(CostScenarioName.COST_0, Decimal("0"), Decimal("0")),
    CostScenarioName.COST_LOW: CostScenario(CostScenarioName.COST_LOW, Decimal("0"), Decimal("5")),
    CostScenarioName.COST_CONSERVATIVE: CostScenario(
        CostScenarioName.COST_CONSERVATIVE, Decimal("0"), Decimal("15")
    ),
}


def get_cost_scenario(name: CostScenarioName) -> CostScenario:
    return SCENARIOS[name]
