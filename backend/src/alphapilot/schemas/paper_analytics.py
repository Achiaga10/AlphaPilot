from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from alphapilot.schemas.portfolio import PaperValidationSchema


class PaperTradeAnalyticsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record: PaperValidationSchema
    evidence_domain: str
    completed_sessions_held: int | None
    calendar_days_held: int
    mfe_percent: Decimal | None
    mae_percent: Decimal | None
    excursion_session_count: int
    actual_exit_vs_signal_close: Decimal | None
    sessions_after_confirmed_exit_signal: int | None
    post_exit_observations: dict[str, dict[str, Any]]
    current_completed_session: date | None
    current_completed_close: Decimal | None
    current_unrealized_pnl: Decimal | None
    current_live_price: Decimal | None
    current_live_freshness: str | None


class PaperStrategyAnalyticsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_profile_id: str | None
    strategy_profile_version: int | None
    open_trade_count: int
    closed_trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate_percent: Decimal | None
    average_return_percent: Decimal | None
    median_return_percent: Decimal | None
    average_winner_return_percent: Decimal | None
    average_loser_return_percent: Decimal | None
    gross_total_pnl: Decimal
    average_calendar_days_held: Decimal | None
    average_entry_adverse_slippage: Decimal | None
    average_quantity_adherence_percent: Decimal | None
    average_mfe_percent: Decimal | None
    mfe_available_count: int
    average_mae_percent: Decimal | None
    mae_available_count: int
    expectancy_return_percent: Decimal | None
    evidence_maturity: str


class ForwardPaperAnalyticsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    evidence_domain: str
    generated_at: datetime
    total_trade_count: int
    open_trade_count: int
    closed_trade_count: int
    wins: int
    losses: int
    breakeven: int
    gross_realized_pnl: Decimal
    win_rate_percent: Decimal | None
    average_return_percent: Decimal | None
    evidence_maturity: str
    complete_evidence_count: int
    partial_evidence_count: int
    legacy_evidence_count: int
    strategy_breakdown: tuple[PaperStrategyAnalyticsSchema, ...]
    open_trades: tuple[PaperTradeAnalyticsSchema, ...]
    closed_trades: tuple[PaperTradeAnalyticsSchema, ...]
