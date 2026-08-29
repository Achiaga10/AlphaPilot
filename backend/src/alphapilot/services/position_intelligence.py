from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import ResearchPositionProvenance
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository
from alphapilot.services.research_portfolio import ResearchPortfolioService
from alphapilot.strategy.profile import resolve_strategy_profile_identity


@dataclass(frozen=True, slots=True)
class PositionIntelligence:
    portfolio_id: UUID
    portfolio_revision: int
    position_id: UUID
    company_id: UUID
    ticker: str
    company_name: str | None
    position_status: str
    provenance_status: str
    quantity: int
    entry_trading_day: date | None
    entry_price: Decimal | None
    average_cost: Decimal
    cost_basis: Decimal
    strategy_guidance_available: bool
    guidance_unavailable_reason: str | None
    strategy: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    strategy_profile_snapshot: dict[str, Any] | None
    selection_policy: str | None
    entry_decision: str | None
    entry_reason: str | None
    latest_completed_trading_day: date | None
    latest_completed_close: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    realized_pnl: Decimal
    monitoring_readiness: str
    monitoring_status: str | None
    monitoring_reason: str
    monitoring_completed_trading_day: date | None
    indicator_facts: dict[str, Any]
    previous_monitoring_status: str | None
    latest_monitoring_transition: str | None
    exit_triggered: bool
    exit_triggered_on: date | None
    exit_trigger_reason: str | None
    active_exit_policy: str | None
    protective_stop_policy: str
    trailing_stop_policy: str
    profit_target_policy: str
    research_only_stop_candidate: str | None
    research_only_stop_status: str | None
    price_change_since_entry: Decimal | None
    explanation: str
    trade_event_count: int
    reconciliation_event_count: int


class PositionIntelligenceService:
    """Read-only assembly boundary for all stored facts about one position."""

    def __init__(self, session: AsyncSession) -> None:
        self.portfolios = ResearchPortfolioRepository(session)
        self.companies = CompanyRepository(session)
        self.valuation = ResearchPortfolioService(session)

    async def get_position_intelligence(
        self, portfolio_id: UUID, position_id: UUID
    ) -> PositionIntelligence:
        portfolio = await self.portfolios.get(portfolio_id)
        position = await self.portfolios.get_position(portfolio_id, position_id)
        if portfolio is None or position is None:
            raise ValueError("Research position not found")
        valuation = await self.valuation.value(portfolio_id)
        valued = next(
            (item for item in valuation.positions if item.position_id == position_id), None
        )
        company = await self.companies.get(position.company_id)
        history = await self.portfolios.monitoring_history(position_id)
        latest = history[0] if history else None
        previous = history[1] if len(history) > 1 else None
        trade_events = await self.portfolios.position_events(position_id)
        reconciliations = await self.portfolios.position_reconciliation_events(position_id)
        realized = sum((Decimal(item.realized_pnl) for item in trade_events), Decimal("0"))

        profile = None
        if (
            position.provenance_status == ResearchPositionProvenance.PLAN_PROFILE.value
            and position.strategy_profile_id
            and position.strategy_profile_version is not None
        ):
            try:
                profile = resolve_strategy_profile_identity(
                    position.strategy_profile_id, position.strategy_profile_version
                )
            except ValueError:
                profile = None
        guidance_available = profile is not None
        monitoring_status = latest.status if guidance_available and latest else None
        monitoring_reason = (
            latest.reason if guidance_available and latest else "STRATEGY_GUIDANCE_UNAVAILABLE"
        )
        transition = None
        if latest and previous and latest.status != previous.status:
            transition = f"{previous.status or 'UNAVAILABLE'}_TO_{latest.status or 'UNAVAILABLE'}"
        reference = position.entry_price or position.average_entry_cost
        change = (
            valued.latest_completed_close - Decimal(reference)
            if valued is not None
            and valued.latest_completed_close is not None
            and reference is not None
            else None
        )
        explanation = self._explanation(monitoring_status, monitoring_reason, guidance_available)
        facts = latest.indicator_facts if latest and guidance_available else {}
        return PositionIntelligence(
            portfolio_id=portfolio.id,
            portfolio_revision=portfolio.revision,
            position_id=position.id,
            company_id=position.company_id,
            ticker=position.ticker_at_entry,
            company_name=company.name if company else None,
            position_status=position.status,
            provenance_status=position.provenance_status,
            quantity=position.quantity,
            entry_trading_day=position.entry_trading_day,
            entry_price=Decimal(position.entry_price) if position.entry_price is not None else None,
            average_cost=Decimal(position.average_entry_cost),
            cost_basis=Decimal(position.cost_basis),
            strategy_guidance_available=guidance_available,
            guidance_unavailable_reason=None if guidance_available else "STRATEGY_PROFILE_UNKNOWN",
            strategy=position.strategy if guidance_available else None,
            strategy_profile_id=position.strategy_profile_id if guidance_available else None,
            strategy_profile_version=(
                position.strategy_profile_version if guidance_available else None
            ),
            strategy_profile_snapshot=(
                position.strategy_profile_snapshot if guidance_available else None
            ),
            selection_policy=position.selection_policy if guidance_available else None,
            entry_decision=position.entry_decision if guidance_available else None,
            entry_reason=position.entry_reason if guidance_available else None,
            latest_completed_trading_day=(valued.latest_completed_trading_day if valued else None),
            latest_completed_close=valued.latest_completed_close if valued else None,
            market_value=valued.market_value if valued else None,
            unrealized_pnl=valued.unrealized_pnl if valued else None,
            unrealized_pnl_pct=valued.unrealized_pnl_pct if valued else None,
            realized_pnl=realized,
            monitoring_readiness=(
                latest.readiness if latest and guidance_available else "UNAVAILABLE"
            ),
            monitoring_status=monitoring_status,
            monitoring_reason=monitoring_reason,
            monitoring_completed_trading_day=(latest.completed_trading_day if latest else None),
            indicator_facts=facts,
            previous_monitoring_status=(
                previous.status if previous and guidance_available else None
            ),
            latest_monitoring_transition=transition if guidance_available else None,
            exit_triggered=bool(position.exit_triggered) if guidance_available else False,
            exit_triggered_on=position.exit_triggered_on if guidance_available else None,
            exit_trigger_reason=position.exit_trigger_reason if guidance_available else None,
            active_exit_policy=profile.strategy_exit_description if profile else None,
            protective_stop_policy="NONE" if profile else "UNAVAILABLE",
            trailing_stop_policy="NONE" if profile else "UNAVAILABLE",
            profit_target_policy="NONE" if profile else "UNAVAILABLE",
            research_only_stop_candidate=(
                profile.research_only_stop_candidate if profile else None
            ),
            research_only_stop_status="NOT_ACTIVE" if profile else None,
            price_change_since_entry=change,
            explanation=explanation,
            trade_event_count=len(trade_events),
            reconciliation_event_count=len(reconciliations),
        )

    @staticmethod
    def _explanation(status: str | None, reason: str, available: bool) -> str:
        if not available:
            return (
                "Strategy guidance is unavailable because Strategy Profile provenance is unknown."
            )
        templates = {
            "EMA20_HELD": "EMA20 is still held.",
            "EMA20_LOST_STRONG_TREND_HOLD": (
                "EMA20 was lost, but the frozen HYBRID strong-trend exception remains active."
            ),
            "EMA50_BREAKDOWN": "EMA50 breakdown triggered the stored strategy exit.",
            "SMA150_INTRADAY_BREACH_RECOVERED": (
                "SMA150 was breached intraday and recovered by the completed close."
            ),
            "SMA150_BREAKDOWN": "SMA150 breakdown triggered the stored strategy exit.",
        }
        return templates.get(
            reason, f"Stored strategy monitoring state is {status or 'unavailable'}."
        )
