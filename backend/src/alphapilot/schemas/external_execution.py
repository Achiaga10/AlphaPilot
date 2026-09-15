"""Typed contracts for user-recorded external execution observations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from alphapilot.database.models.external_execution import (
    ExternalActionStatus,
    ExternalReconciliationStatus,
)
from alphapilot.database.models.forward_portfolio import ForwardOrderStatus
from alphapilot.schemas.broker_sync import BrokerExecutionSchema, BrokerMatchStateValue


class ExternalSkipReason(StrEnum):
    USER_SKIPPED = "USER_SKIPPED"
    MISSED_ENTRY = "MISSED_ENTRY"
    BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"
    MANUAL_RISK_DECISION = "MANUAL_RISK_DECISION"
    OTHER = "OTHER"


class ExternalFillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=120)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    executed_at: AwareDatetime
    fee: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    mark_complete: bool = True


class ExternalSkipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    reason: ExternalSkipReason


class ExternalVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    request_key: str = Field(min_length=8, max_length=120)
    reason: str = Field(min_length=3, max_length=200)


class ExternalFillSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_key: str
    side: Literal["BUY", "SELL"]
    quantity: int
    price: Decimal
    executed_at: AwareDatetime
    fee: Decimal | None
    mark_complete: bool
    source: str
    created_at: AwareDatetime
    voided_at: AwareDatetime | None
    void_reason: str | None
    void_source: str | None


class ExternalEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: str
    reason_code: str
    source: str
    facts: dict[str, Any]
    created_at: AwareDatetime


class ExternalActionSchema(BaseModel):
    id: UUID
    forward_portfolio_id: UUID
    forward_order_id: UUID
    position_id: UUID | None
    ticker: str
    side: Literal["BUY", "SELL"]
    strategy_id: str
    strategy_version: int
    broker: str
    provenance: str
    canonical_execution_source: Literal["NONE", "MANUAL_USER_RECORDED", "ALPACA_READ_ONLY_SYNC"]
    broker_match_state: BrokerMatchStateValue | None
    source_signal_session: date
    planned_execution_session: date | None
    actual_virtual_execution_session: date | None
    expected_timing: str
    planned_shares: int
    virtual_filled_shares: int | None
    virtual_order_status: ForwardOrderStatus
    virtual_modeled_fill_price: Decimal | None
    loss_control_policy: str
    loss_control_boundary: Decimal | None
    decision_reason: str
    created_at: AwareDatetime
    status: ExternalActionStatus
    reconciliation_status: ExternalReconciliationStatus
    due_status: Literal["UPCOMING", "AWAITING_RECORD", "OVERDUE_RECORDING", "DONE", "CANCELLED"]
    recorded_shares: Decimal
    weighted_fill_price: Decimal | None
    recorded_notional: Decimal | None
    recorded_fees: Decimal | None
    fee_coverage_complete: bool
    share_variance_vs_planned: Decimal | None
    share_variance_vs_virtual: Decimal | None
    price_difference_per_share: Decimal | None
    price_difference_bps: Decimal | None
    virtual_notional: Decimal | None
    notional_variance: Decimal | None
    first_executed_at: AwareDatetime | None
    timing_difference_seconds: int | None
    skip_reason: str | None
    fills: list[ExternalFillSchema]
    broker_executions: list[BrokerExecutionSchema]
    events: list[ExternalEventSchema]


class ExternalTradeComparisonSchema(BaseModel):
    forward_trade_id: UUID
    ticker: str
    entry_action_id: UUID | None
    exit_action_id: UUID | None
    completeness: Literal[
        "COMPLETE",
        "MISSING_ENTRY",
        "MISSING_EXIT",
        "PARTIAL",
        "QUANTITY_MISMATCH",
        "FEES_UNKNOWN",
        "SKIPPED",
    ]
    virtual_shares: int
    recorded_entry_shares: Decimal | None
    recorded_exit_shares: Decimal | None
    virtual_entry_price: Decimal
    recorded_entry_price: Decimal | None
    virtual_exit_price: Decimal
    recorded_exit_price: Decimal | None
    virtual_net_pnl: Decimal
    recorded_gross_pnl: Decimal | None
    recorded_execution_pnl: Decimal | None
    pnl_difference: Decimal | None
    recorded_fees: Decimal | None
    entry_price_difference: Decimal | None
    exit_price_difference: Decimal | None
    quantity_variance: Decimal | None


class ExternalExecutionAnalyticsSchema(BaseModel):
    expected_actions: int
    recorded_actions: int
    skipped_actions: int
    missing_records: int
    partial_actions: int
    actions_awaiting_execution: int
    actions_awaiting_recording: int
    diverged_actions: int
    recording_rate_pct: Decimal | None
    skip_rate_pct: Decimal | None
    average_absolute_entry_difference_bps: Decimal | None
    average_signed_entry_difference_bps: Decimal | None
    average_absolute_exit_difference_bps: Decimal | None
    average_signed_exit_difference_bps: Decimal | None
    average_quantity_variance: Decimal | None
    completed_fully_reconciled_trades: int
    matched_virtual_pnl: Decimal | None
    matched_recorded_execution_pnl: Decimal | None
    matched_pnl_difference: Decimal | None
    manual_actions: int = 0
    broker_actions: int = 0
    conflict_actions: int = 0
