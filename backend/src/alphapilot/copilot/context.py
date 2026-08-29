from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.portfolio.stop_exit_guidance import StopExitGuidanceService
from alphapilot.services.paper_validation import PaperValidationService
from alphapilot.services.position_intelligence import PositionIntelligenceService
from alphapilot.services.research_portfolio import ResearchPortfolioService


@dataclass(frozen=True, slots=True)
class CopilotContext:
    scope: str
    portfolio_id: UUID
    position_id: UUID | None
    ticker: str | None
    as_of_date: date | None
    facts: dict[str, dict[str, Any]]
    limitations: tuple[str, ...]


class CopilotContextAssembler:
    """Assemble canonical read-only facts; no ORM object crosses this boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self.intelligence = PositionIntelligenceService(session)
        self.papers = PaperValidationService(session)
        self.portfolios = ResearchPortfolioService(session)
        self.guidance = StopExitGuidanceService()

    async def position(self, portfolio_id: UUID, position_id: UUID) -> CopilotContext:
        item = await self.intelligence.get_position_intelligence(portfolio_id, position_id)
        guidance = self.guidance.build(item)
        papers = await self.papers.list(portfolio_id, position_id=position_id)
        facts: dict[str, dict[str, Any]] = {}

        def add(identifier: str, source: str, field: str, value: Any, label: str) -> None:
            facts[identifier] = {
                "source": source,
                "field": field,
                "label": label,
                "value": value,
            }

        add("position.ticker", "position_intelligence", "ticker", item.ticker, "Ticker")
        add(
            "position.profile",
            "position_intelligence",
            "strategy_profile_id",
            item.strategy_profile_id,
            "Strategy Profile",
        )
        add(
            "position.monitoring_status",
            "position_intelligence",
            "monitoring_status",
            item.monitoring_status,
            "Monitoring",
        )
        add(
            "position.monitoring_reason",
            "position_intelligence",
            "monitoring_reason",
            item.monitoring_reason,
            "Monitoring reason",
        )
        add(
            "guidance.protective_stop",
            "stop_exit_guidance",
            "protective_stop",
            guidance.protective_stop,
            "Active protective stop",
        )
        add(
            "guidance.trailing_stop",
            "stop_exit_guidance",
            "trailing_stop",
            guidance.trailing_stop,
            "Trailing stop",
        )
        add(
            "guidance.profit_target",
            "stop_exit_guidance",
            "profit_target",
            guidance.profit_target,
            "Profit target",
        )
        add(
            "guidance.completed_session",
            "stop_exit_guidance",
            "as_of_date",
            guidance.as_of_date,
            "Completed session",
        )
        add(
            "guidance.research_only",
            "stop_exit_guidance",
            "research_only_candidate",
            {
                "candidate": guidance.research_only_candidate,
                "status": guidance.research_only_status,
            },
            "Research-only stop evidence",
        )
        for index, reference in enumerate(guidance.references):
            add(
                f"guidance.reference.{index}",
                "stop_exit_guidance",
                "references",
                asdict(reference),
                reference.reference_type.value,
            )
        for index, paper in enumerate(papers):
            add(
                f"paper.{index}",
                "paper_validation",
                "comparison",
                {
                    "status": paper.status,
                    "reference_entry_price": paper.reference_entry_price,
                    "actual_entry_price": paper.actual_entry_price,
                    "entry_fill_difference": paper.entry_fill_difference,
                    "entry_fill_difference_bps": paper.entry_fill_difference_bps,
                    "actual_exit_price": paper.actual_exit_price,
                    "paper_gross_pnl": paper.paper_gross_pnl,
                    "paper_gross_return_pct": paper.paper_gross_return_pct,
                },
                "Alpaca Paper validation",
            )
        limitations = (
            "Explanatory research only; no broker order or portfolio mutation.",
            "Daily strategy references require a completed session and are not intraday stops.",
        )
        return CopilotContext(
            "POSITION",
            portfolio_id,
            position_id,
            item.ticker,
            guidance.as_of_date,
            facts,
            limitations,
        )

    async def portfolio(self, portfolio_id: UUID) -> CopilotContext:
        valuation = await self.portfolios.value(portfolio_id)
        facts: dict[str, dict[str, Any]] = {
            "portfolio.value": {
                "source": "portfolio_context",
                "field": "total_equity",
                "label": "Portfolio value",
                "value": valuation.total_equity,
            },
            "portfolio.cash": {
                "source": "portfolio_context",
                "field": "cash",
                "label": "Cash",
                "value": valuation.cash,
            },
        }
        statuses: list[dict[str, Any]] = []
        for position in valuation.positions:
            intelligence = await self.intelligence.get_position_intelligence(
                portfolio_id, position.position_id
            )
            statuses.append(
                {
                    "ticker": intelligence.ticker,
                    "status": intelligence.monitoring_status,
                    "reason": intelligence.monitoring_reason,
                    "exit_triggered": intelligence.exit_triggered,
                }
            )
        facts["portfolio.monitoring"] = {
            "source": "portfolio_context",
            "field": "position_monitoring",
            "label": "Position monitoring",
            "value": statuses,
        }
        return CopilotContext(
            "PORTFOLIO",
            portfolio_id,
            None,
            None,
            valuation.latest_completed_trading_day,
            facts,
            ("Explanatory research only; no broker order or portfolio mutation.",),
        )
