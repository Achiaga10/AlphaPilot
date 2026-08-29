from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import (
    PaperExecutionSource,
    PaperValidationRecord,
    PaperValidationStatus,
)
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository


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


class PaperValidationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.portfolios = ResearchPortfolioRepository(session)

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
        position = await self.portfolios.get_position(portfolio_id, position_id)
        if position is None:
            raise ValueError("Research position not found")
        existing = await self.portfolios.list_paper_validations(
            portfolio_id, position_id=position_id
        )
        if any(item.status == PaperValidationStatus.OPEN.value for item in existing):
            raise ValueError("An open paper validation already exists for this position")
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
            planned_quantity=(position.quantity if position.strategy_profile_id else None),
            reference_entry_price=(position.entry_price if position.strategy_profile_id else None),
            actual_quantity=actual_quantity,
            actual_entry_price=actual_entry_price,
            actual_entry_at=actual_entry_at,
            entry_note=note,
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
        record.status = PaperValidationStatus.CLOSED.value
        record.actual_exit_quantity = actual_exit_quantity
        record.actual_exit_price = actual_exit_price
        record.actual_exit_at = actual_exit_at
        record.exit_note = note
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
        )
