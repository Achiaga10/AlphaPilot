from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import (
    PaperExecutionSource,
    PaperValidationRecord,
    PaperValidationStatus,
)
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository
from alphapilot.services.live_portfolio import live_market_cache
from alphapilot.services.position_intelligence import PositionIntelligenceService

EVIDENCE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PaperValidationView:
    id: UUID
    portfolio_id: UUID
    position_id: UUID
    ticker: str
    status: str
    execution_source: str
    position_provenance: str
    strategy: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    entry_decision: str | None
    entry_reason: str | None
    recommendation_day: object | None
    planned_quantity: int | None
    reference_entry_price: Decimal | None
    actual_quantity: int
    actual_entry_price: Decimal
    actual_entry_at: datetime
    entry_note: str | None
    entry_fill_difference: Decimal | None
    entry_fill_difference_bps: Decimal | None
    quantity_difference: int | None
    actual_exit_quantity: int | None
    actual_exit_price: Decimal | None
    actual_exit_at: datetime | None
    exit_note: str | None
    paper_entry_value: Decimal
    paper_exit_value: Decimal | None
    paper_gross_pnl: Decimal | None
    paper_gross_return_pct: Decimal | None
    alphapilot_exit_triggered_on: object | None
    alphapilot_exit_reason: str | None
    alphapilot_trigger_close: Decimal | None
    evidence_completeness: str
    entry_evidence_schema_version: int | None
    entry_evidence: dict[str, Any] | None
    exit_evidence_schema_version: int | None
    exit_evidence: dict[str, Any] | None
    entry_slippage_percent: Decimal | None
    entry_adverse_slippage_dollars_per_share: Decimal | None
    quantity_adherence_percent: Decimal | None
    planned_notional: Decimal | None
    actual_entry_notional: Decimal
    fees_available: bool
    net_paper_pnl: Decimal | None
    calendar_days_held: int | None


class PaperValidationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.portfolios = ResearchPortfolioRepository(session)
        self.intelligence = PositionIntelligenceService(session)

    async def record_entry(
        self,
        *,
        portfolio_id: UUID,
        position_id: UUID,
        actual_quantity: int,
        actual_entry_price: Decimal,
        actual_entry_at: datetime,
        note: str | None,
    ) -> PaperValidationView:
        if actual_quantity <= 0 or actual_entry_price <= 0:
            raise ValueError("Paper entry requires positive whole shares and fill price")
        actual_entry_at = self._utc_execution_instant(actual_entry_at)
        position = await self.portfolios.get_position(portfolio_id, position_id)
        if position is None:
            raise ValueError("Research position not found")
        existing = await self.portfolios.list_paper_validations(
            portfolio_id, position_id=position_id
        )
        if any(item.status == PaperValidationStatus.OPEN.value for item in existing):
            raise ValueError("An open paper validation already exists for this position")
        evidence = await self._capture_evidence(portfolio_id, position_id)
        evidence["actual_execution"] = {
            "quantity": actual_quantity,
            "fill_price": str(actual_entry_price),
            "executed_at": actual_entry_at.isoformat(),
            "source": PaperExecutionSource.ALPACA_PAPER_MANUAL.value,
        }
        planned = evidence["planned_execution"]
        record = PaperValidationRecord(
            portfolio_id=portfolio_id,
            position_id=position.id,
            company_id=position.company_id,
            ticker=position.ticker_at_entry,
            status=PaperValidationStatus.OPEN.value,
            execution_source=PaperExecutionSource.ALPACA_PAPER_MANUAL.value,
            position_provenance=position.provenance_status,
            strategy=position.strategy,
            strategy_profile_id=position.strategy_profile_id,
            strategy_profile_version=position.strategy_profile_version,
            entry_decision=position.entry_decision,
            entry_reason=position.entry_reason,
            recommendation_day=position.entry_trading_day,
            planned_quantity=(
                int(planned["planned_quantity"])
                if position.strategy_profile_id and planned["planned_quantity"] is not None
                else None
            ),
            reference_entry_price=(
                Decimal(planned["planned_reference_price"])
                if position.strategy_profile_id and planned["planned_reference_price"] is not None
                else None
            ),
            actual_quantity=actual_quantity,
            actual_entry_price=actual_entry_price,
            actual_entry_at=actual_entry_at,
            entry_note=note,
            entry_evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
            entry_evidence=evidence,
        )
        self.portfolios.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return self._view(record)

    async def list(
        self, portfolio_id: UUID, *, position_id: UUID | None = None
    ) -> list[PaperValidationView]:
        return [
            self._view(item)
            for item in await self.portfolios.list_paper_validations(
                portfolio_id, position_id=position_id
            )
        ]

    async def record_exit(
        self,
        *,
        portfolio_id: UUID,
        validation_id: UUID,
        actual_exit_quantity: int,
        actual_exit_price: Decimal,
        actual_exit_at: datetime,
        note: str | None,
    ) -> PaperValidationView:
        actual_exit_at = self._utc_execution_instant(actual_exit_at)
        record = await self.portfolios.get_paper_validation(
            portfolio_id, validation_id, for_update=True
        )
        if record is None:
            raise ValueError("Paper validation not found")
        if record.status != PaperValidationStatus.OPEN.value:
            raise ValueError("Paper validation is already closed")
        if actual_exit_quantity != record.actual_quantity:
            raise ValueError("V1 paper validation requires one full aggregated exit")
        if actual_exit_price <= 0:
            raise ValueError("Paper exit price must be positive")
        position = await self.portfolios.get_position(portfolio_id, record.position_id)
        exit_evidence = await self._capture_evidence(portfolio_id, record.position_id)
        exit_evidence["actual_execution"] = {
            "quantity": actual_exit_quantity,
            "fill_price": str(actual_exit_price),
            "executed_at": actual_exit_at.isoformat(),
            "source": PaperExecutionSource.ALPACA_PAPER_MANUAL.value,
        }
        record.status = PaperValidationStatus.CLOSED.value
        record.actual_exit_quantity = actual_exit_quantity
        record.actual_exit_price = actual_exit_price
        record.actual_exit_at = actual_exit_at
        record.exit_note = note
        record.exit_evidence_schema_version = EVIDENCE_SCHEMA_VERSION
        record.exit_evidence = exit_evidence
        if position is not None and position.exit_triggered:
            record.alphapilot_exit_triggered_on = position.exit_triggered_on
            record.alphapilot_exit_reason = position.exit_trigger_reason
            history = await self.portfolios.monitoring_history(position.id)
            trigger = next(
                (
                    item
                    for item in history
                    if item.completed_trading_day == position.exit_triggered_on
                ),
                None,
            )
            record.alphapilot_trigger_close = trigger.latest_close if trigger else None
        await self.session.commit()
        await self.session.refresh(record)
        return self._view(record)

    @staticmethod
    def _utc_execution_instant(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Paper execution timestamp must include a timezone offset")
        return value.astimezone(UTC)

    async def _capture_evidence(self, portfolio_id: UUID, position_id: UUID) -> dict[str, Any]:
        position = await self.portfolios.get_position(portfolio_id, position_id)
        if position is None:
            raise ValueError("Research position not found")
        facts = await self.intelligence.get_position_intelligence(portfolio_id, position_id)
        events = await self.portfolios.position_events(position_id)
        opening = next((item for item in events if item.event_type == "OPEN"), None)
        live = live_market_cache.position(portfolio_id, position_id)
        valid_live = (
            live
            if live is not None
            and live.live is not None
            and live.live.freshness.value not in {"STALE", "UNKNOWN"}
            else None
        )
        indicator = facts.indicator_facts
        return {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "captured_at": datetime.now(UTC).isoformat(),
            "identity": {
                "ticker": facts.ticker,
                "company_id": str(facts.company_id),
                "position_id": str(position_id),
            },
            "decision": {
                "strategy": facts.strategy,
                "strategy_profile_id": facts.strategy_profile_id,
                "strategy_profile_version": facts.strategy_profile_version,
                "source_action_id": opening.action_id if opening else None,
                "source_plan_id": None,
                "portfolio_revision": facts.portfolio_revision,
                "entry_decision": facts.entry_decision,
                "entry_reason": facts.entry_reason,
                "selection_policy": facts.selection_policy,
                "recommendation_day": self._iso(facts.entry_trading_day),
                "news_overlay": position.entry_decision_evidence,
            },
            "planned_execution": {
                "planned_quantity": opening.quantity if opening else facts.quantity,
                "planned_reference_price": self._decimal(
                    opening.execution_price if opening else facts.entry_price
                ),
                "sizing_policy": None,
                "sector": None,
                "execution_readiness": None,
                "readiness_reason": None,
            },
            "loss_control": {
                "policy": facts.loss_control_policy,
                "boundary": self._decimal(facts.current_loss_control_boundary),
                "trigger": facts.loss_control_trigger,
                "broker_stop_order": facts.loss_control_broker_stop_order,
                "active_exit_policy": facts.active_exit_policy,
            },
            "completed_state": {
                "session": self._iso(facts.latest_completed_trading_day),
                "close": self._decimal(facts.latest_completed_close),
                "ema20": self._json_fact(indicator.get("ema20")),
                "ema50": self._json_fact(indicator.get("ema50")),
                "sma150": self._json_fact(indicator.get("sma150")),
                "atr14": self._json_fact(indicator.get("atr14")),
                "monitoring_status": facts.monitoring_status,
                "monitoring_reason": facts.monitoring_reason,
                "exit_triggered": facts.exit_triggered,
                "exit_triggered_on": self._iso(facts.exit_triggered_on),
                "exit_trigger_reason": facts.exit_trigger_reason,
            },
            "live_state": self._live_evidence(valid_live),
        }

    @staticmethod
    def _live_evidence(item: Any | None) -> dict[str, Any] | None:
        if item is None or item.live is None:
            return None
        return {
            "price": str(item.live.last_price),
            "provider_timestamp": item.live.quote_timestamp.isoformat(),
            "provider": item.live.provider,
            "feed": item.live.feed,
            "freshness": item.live.freshness.value,
            "provisional_ema20": PaperValidationService._decimal(item.provisional_ema20),
            "provisional_ema50": PaperValidationService._decimal(item.provisional_ema50),
            "provisional_sma150": PaperValidationService._decimal(item.provisional_sma150),
            "provisional_atr14": PaperValidationService._decimal(item.provisional_atr14),
            "live_status": item.live_status.value,
            "projected_signal_if_closed_now": item.projected_signal_if_closed_now,
            "projected_reason": item.projected_reason,
            "projection_is_official": False,
        }

    @staticmethod
    def _decimal(value: Any | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _iso(value: date | datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _json_fact(value: Any | None) -> Any | None:
        return str(value) if isinstance(value, Decimal) else value

    @staticmethod
    def _view(record: PaperValidationRecord) -> PaperValidationView:
        reference = (
            Decimal(record.reference_entry_price)
            if record.reference_entry_price is not None
            else None
        )
        actual_entry = Decimal(record.actual_entry_price)
        difference = actual_entry - reference if reference is not None else None
        difference_bps = (
            difference / reference * Decimal("10000")
            if difference is not None and reference is not None and reference != 0
            else None
        )
        entry_value = Decimal(record.actual_quantity) * actual_entry
        exit_price = (
            Decimal(record.actual_exit_price) if record.actual_exit_price is not None else None
        )
        exit_value = (
            Decimal(record.actual_exit_quantity or 0) * exit_price
            if exit_price is not None
            else None
        )
        pnl = exit_value - entry_value if exit_value is not None else None
        planned_quantity = record.planned_quantity
        planned_notional = (
            Decimal(planned_quantity) * reference
            if planned_quantity is not None and reference is not None
            else None
        )
        evidence_completeness = (
            "LEGACY"
            if record.entry_evidence_schema_version is None
            else "FULL"
            if record.strategy_profile_id and planned_quantity is not None and reference is not None
            else "PARTIAL"
        )
        return PaperValidationView(
            id=record.id,
            portfolio_id=record.portfolio_id,
            position_id=record.position_id,
            ticker=record.ticker,
            status=record.status,
            execution_source=record.execution_source,
            position_provenance=record.position_provenance,
            strategy=record.strategy,
            strategy_profile_id=record.strategy_profile_id,
            strategy_profile_version=record.strategy_profile_version,
            entry_decision=record.entry_decision,
            entry_reason=record.entry_reason,
            recommendation_day=record.recommendation_day,
            planned_quantity=record.planned_quantity,
            reference_entry_price=reference,
            actual_quantity=record.actual_quantity,
            actual_entry_price=actual_entry,
            actual_entry_at=record.actual_entry_at,
            entry_note=record.entry_note,
            entry_fill_difference=difference,
            entry_fill_difference_bps=difference_bps,
            quantity_difference=(
                record.actual_quantity - record.planned_quantity
                if record.planned_quantity is not None
                else None
            ),
            actual_exit_quantity=record.actual_exit_quantity,
            actual_exit_price=exit_price,
            actual_exit_at=record.actual_exit_at,
            exit_note=record.exit_note,
            paper_entry_value=entry_value,
            paper_exit_value=exit_value,
            paper_gross_pnl=pnl,
            paper_gross_return_pct=(
                pnl / entry_value * Decimal("100") if pnl is not None else None
            ),
            alphapilot_exit_triggered_on=record.alphapilot_exit_triggered_on,
            alphapilot_exit_reason=record.alphapilot_exit_reason,
            alphapilot_trigger_close=(
                Decimal(record.alphapilot_trigger_close)
                if record.alphapilot_trigger_close is not None
                else None
            ),
            evidence_completeness=evidence_completeness,
            entry_evidence_schema_version=record.entry_evidence_schema_version,
            entry_evidence=record.entry_evidence,
            exit_evidence_schema_version=record.exit_evidence_schema_version,
            exit_evidence=record.exit_evidence,
            entry_slippage_percent=(
                (actual_entry / reference - Decimal("1")) * Decimal("100")
                if reference is not None and reference != 0
                else None
            ),
            entry_adverse_slippage_dollars_per_share=difference,
            quantity_adherence_percent=(
                Decimal(record.actual_quantity) / Decimal(planned_quantity) * Decimal("100")
                if planned_quantity is not None and planned_quantity > 0
                else None
            ),
            planned_notional=planned_notional,
            actual_entry_notional=entry_value,
            fees_available=False,
            net_paper_pnl=None,
            calendar_days_held=(
                (record.actual_exit_at.date() - record.actual_entry_at.date()).days
                if record.actual_exit_at is not None
                else None
            ),
        )
