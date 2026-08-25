from decimal import Decimal

from alphapilot.backtesting.cost_scenarios import CostScenarioName, get_cost_scenario


def test_cost_scenarios_are_fixed_and_deterministic() -> None:
    assert get_cost_scenario(CostScenarioName.COST_0).slippage_bps == Decimal("0")
    assert get_cost_scenario(CostScenarioName.COST_LOW).slippage_bps == Decimal("5")
    assert get_cost_scenario(CostScenarioName.COST_CONSERVATIVE).slippage_bps == Decimal("15")
    assert get_cost_scenario(CostScenarioName.COST_LOW) == get_cost_scenario(
        CostScenarioName.COST_LOW
    )
    assert all(get_cost_scenario(name).commission_per_order == 0 for name in CostScenarioName)
