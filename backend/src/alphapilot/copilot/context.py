from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.copilot.navigation import navigation_facts
from alphapilot.portfolio.stop_exit_guidance import StopExitGuidanceService
from alphapilot.services.live_portfolio import live_market_cache
from alphapilot.services.paper_analytics import ForwardPaperAnalyticsService
from alphapilot.services.paper_validation import PaperValidationService
from alphapilot.services.position_intelligence import PositionIntelligenceService
from alphapilot.services.research_portfolio import ResearchPortfolioService


@dataclass(frozen=True, slots=True)
class CopilotContext:
    scope: str
    portfolio_id: UUID | None
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
        self.paper_analytics = ForwardPaperAnalyticsService(session)
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
            "position.average_cost",
            "position_intelligence",
            "average_cost",
            item.average_cost,
            "Average cost per share",
        )
        add("position.quantity", "position_intelligence", "quantity", item.quantity, "Quantity")
        add(
            "position.entry_price",
            "position_intelligence",
            "entry_price",
            item.entry_price,
            "Entry price",
        )
        add(
            "position.latest_completed_close",
            "position_intelligence",
            "latest_completed_close",
            item.latest_completed_close,
            "Latest completed close",
        )
        add(
            "position.market_value",
            "position_intelligence",
            "market_value",
            item.market_value,
            "Market value",
        )
        add(
            "position.unrealized_pnl",
            "position_intelligence",
            "unrealized_pnl",
            item.unrealized_pnl,
            "Unrealized P&L",
        )
        add(
            "position.unrealized_pnl_pct",
            "position_intelligence",
            "unrealized_pnl_pct",
            item.unrealized_pnl_pct,
            "Unrealized P&L percent",
        )
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
        live = live_market_cache.position(portfolio_id, position_id)
        if live is not None:
            live_facts = {
                "price": live.live.last_price if live.live else None,
                "high": live.live.session_high if live.live else None,
                "low": live.live.session_low if live.live else None,
                "timestamp": live.live.quote_timestamp if live.live else None,
                "freshness": live.live.freshness if live.live else "UNAVAILABLE",
                "coverage": live.live.coverage_note if live.live else None,
                "completed_ema20": live.completed_ema20,
                "provisional_ema20": live.provisional_ema20,
                "completed_ema50": live.completed_ema50,
                "provisional_ema50": live.provisional_ema50,
                "completed_sma150": live.completed_sma150,
                "provisional_sma150": live.provisional_sma150,
                "completed_atr14": live.completed_atr14,
                "provisional_atr14": live.provisional_atr14,
                "distance_to_ema20_dollars": live.distance_to_ema20_dollars,
                "distance_to_ema20_pct": live.distance_to_ema20_pct,
                "distance_to_ema50_dollars": live.distance_to_ema50_dollars,
                "distance_to_ema50_pct": live.distance_to_ema50_pct,
                "live_status": live.live_status,
                "live_reason": live.live_reason,
                "projected_signal": live.projected_signal_if_closed_now,
                "projected_reason": live.projected_reason,
                "projection_is_official": live.projection_is_official,
                "confirmed_sell_required": live.confirmed_sell_required,
                "completed_session": live.completed_session,
            }
            for field, value in live_facts.items():
                add(
                    f"live.{field}",
                    "live_market_cache",
                    field,
                    value,
                    field.replace("_", " ").title(),
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
        add(
            "guidance.loss_control",
            "stop_exit_guidance",
            "loss_control",
            {
                "policy": guidance.loss_control_policy,
                "boundary": guidance.current_loss_control_boundary,
                "trigger": guidance.loss_control_trigger,
                "active": guidance.loss_control_active,
                "broker_stop_order": guidance.broker_stop_order,
            },
            "Active strategy loss control",
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
                    "entry_slippage_percent": paper.entry_slippage_percent,
                    "quantity_adherence_percent": paper.quantity_adherence_percent,
                    "planned_notional": paper.planned_notional,
                    "actual_entry_notional": paper.actual_entry_notional,
                    "evidence_completeness": paper.evidence_completeness,
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

    def general(self) -> CopilotContext:
        return CopilotContext(
            "GENERAL",
            None,
            None,
            None,
            None,
            navigation_facts(),
            ("Read-only product help; no sync, portfolio mutation, or order is performed.",),
        )

    async def portfolio(self, portfolio_id: UUID) -> CopilotContext:
        valuation = await self.portfolios.value(portfolio_id)
        paper = await self.paper_analytics.summary(portfolio_id)
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
        facts["paper_analytics.summary"] = {
            "source": "forward_paper_analytics",
            "field": "summary",
            "label": "Forward Paper Evidence summary",
            "value": {
                "open_trade_count": paper.open_trade_count,
                "closed_trade_count": paper.closed_trade_count,
                "gross_realized_pnl": paper.gross_realized_pnl,
                "win_rate_percent": paper.win_rate_percent,
                "evidence_maturity": paper.evidence_maturity,
            },
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
