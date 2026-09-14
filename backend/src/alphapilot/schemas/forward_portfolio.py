from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from alphapilot.database.models.forward_portfolio import (
    ForwardBrokerExecutionMode,
    ForwardCycleStatus,
    ForwardExecutionMode,
    ForwardOrderSide,
    ForwardOrderStatus,
    ForwardPortfolioStatus,
    ForwardPositionStatus,
)
from alphapilot.services.forward_portfolio_scheduler import ForwardSchedulerRunStatus


class ForwardPortfolioInitializeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_cash: Decimal = Field(gt=0)
    forward_start_session: date


class ForwardPortfolioMutationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    confirmed: bool


class ForwardPortfolioSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    strategy_id: str
    strategy_version: int
    execution_mode: ForwardExecutionMode
    broker_execution_mode: ForwardBrokerExecutionMode
    status: ForwardPortfolioStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
    forward_start_session: date
    initial_cash: Decimal
    cash_balance: Decimal
    equity: Decimal
    realized_pnl: Decimal
    revision: int
    last_processed_session: date | None
    last_successful_cycle: AwareDatetime | None
    last_error: str | None


class ForwardOrderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticker: str
    side: ForwardOrderSide
    status: ForwardOrderStatus
    source_signal_session: date
    planned_execution_session: date | None
    actual_execution_session: date | None
    approved_allocation: Decimal
    planned_shares: int
    filled_shares: int | None
    raw_fill_price: Decimal | None
    modeled_fill_price: Decimal | None
    friction_bps: Decimal
    friction_dollars: Decimal | None
    reason_code: str
    strategy_id: str
    strategy_version: int
    ranking_score: Decimal | None
    ranking_position: int | None
    loss_control_policy: str
    loss_control_boundary: Decimal | None
    loss_control_trigger: str | None
    risk_per_share: Decimal | None
    planned_risk_dollars: Decimal | None
    planned_risk_pct: Decimal | None
    evidence: dict[str, Any]
    created_at: AwareDatetime


class ForwardPositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticker: str
    status: ForwardPositionStatus
    shares: int
    signal_session: date
    entry_session: date
    raw_entry_price: Decimal
    modeled_entry_price: Decimal
    entry_friction: Decimal
    cost_basis: Decimal
    last_mark_session: date
    last_close: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_return_pct: Decimal
    loss_control_policy: str
    loss_control_boundary: Decimal
    loss_control_trigger: str
    loss_control_source: str
    risk_per_share: Decimal
    planned_risk_dollars: Decimal
    holding_sessions: int
    holding_calendar_days: int
    exit_signal_session: date | None
    closed_session: date | None
    management_status: str


class ForwardTradeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticker: str
    strategy_id: str
    strategy_version: int
    signal_session: date
    entry_session: date
    raw_entry_price: Decimal
    modeled_entry_price: Decimal
    entry_friction: Decimal
    approved_allocation: Decimal
    shares: int
    loss_control_policy: str
    initial_loss_control_boundary: Decimal
    loss_control_trigger: str
    loss_control_source: str
    risk_per_share: Decimal
    planned_risk_dollars: Decimal
    entry_evidence: dict[str, Any]
    exit_signal_session: date
    exit_session: date
    raw_exit_price: Decimal
    modeled_exit_price: Decimal
    exit_friction: Decimal
    exit_reason: str
    gross_pnl: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    holding_sessions: int
    holding_calendar_days: int


class ForwardEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    trading_session: date | None
    ticker: str | None
    strategy_id: str
    reason_code: str
    numeric_provenance: dict[str, Any]
    created_at: AwareDatetime


class ForwardAnalyticsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    starting_equity: Decimal
    current_equity: Decimal
    cash: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    net_return_pct: Decimal
    max_drawdown_pct: Decimal
    completed_trades: int
    open_trades: int
    win_rate_pct: Decimal | None
    profit_factor: Decimal | None
    expectancy: Decimal | None
    average_winner: Decimal | None
    average_loser: Decimal | None
    worst_trade: Decimal | None
    average_holding_sessions: Decimal | None
    turnover_pct: Decimal
    friction_dollars: Decimal
    current_exposure_pct: Decimal
    average_exposure_pct: Decimal | None
    max_concurrent_positions: int
    stop_exits: int
    strategy_exits: int


class ForwardCycleTriggerResultSchema(BaseModel):
    portfolio_id: UUID | None
    latest_completed_market_session: date | None
    processed_sessions: list[date]
    skipped_sessions: list[date]


class ForwardHealthSchema(BaseModel):
    scheduler_running: bool
    scheduler_status: ForwardSchedulerRunStatus
    portfolio_status: ForwardPortfolioStatus | None
    last_successful_cycle: AwareDatetime | None
    last_processed_session: date | None
    latest_completed_market_session: date | None
    pending_sessions: int
    data_ready: bool
    last_error: str | None
    latest_cycle_status: ForwardCycleStatus | None = None
