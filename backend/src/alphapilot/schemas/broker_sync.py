"""Public contracts for observational Alpaca read-only synchronization."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

BrokerMatchStateValue = Literal[
    "UNMATCHED",
    "AUTO_MATCHED",
    "AMBIGUOUS",
    "MANUAL_MATCHED",
    "IGNORED_EXTERNAL",
    "CONFLICT",
]


class AlpacaSyncStatusSchema(BaseModel):
    enabled: bool
    configured: bool
    environment: Literal["PAPER", "LIVE"]
    scheduler_running: bool
    status: str
    last_attempt_at: AwareDatetime | None
    last_success_at: AwareDatetime | None
    last_error: str | None
    data_age_seconds: int | None
    account_snapshots: int
    positions: int
    orders: int
    executions: int
    unmatched_executions: int
    interval_seconds: int
    initial_lookback_days: int
    overlap_minutes: int
    provenance: Literal["ALPACA_READ_ONLY_SYNC"] = "ALPACA_READ_ONLY_SYNC"


class BrokerAccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    environment: Literal["PAPER", "LIVE"]
    status: str
    currency: str
    cash: Decimal
    equity: Decimal
    buying_power: Decimal
    observed_at: AwareDatetime


class BrokerPositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    environment: Literal["PAPER", "LIVE"]
    symbol: str
    side: str
    quantity: Decimal
    average_entry_price: Decimal | None
    current_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    observed_at: AwareDatetime


class BrokerOrderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    environment: Literal["PAPER", "LIVE"]
    broker_order_id: str
    client_order_id: str | None
    symbol: str
    side: str
    status: str
    order_type: str
    quantity: Decimal | None
    filled_quantity: Decimal
    filled_average_price: Decimal | None
    submitted_at: AwareDatetime | None
    broker_updated_at: AwareDatetime | None


class BrokerExecutionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provenance: str
    environment: Literal["PAPER", "LIVE"]
    broker_activity_id: str
    broker_order_id: str | None
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    price: Decimal
    fee: Decimal | None
    executed_at: AwareDatetime
    match_state: BrokerMatchStateValue
    match_reason: str
    external_case_id: UUID | None
    matched_at: AwareDatetime | None
    ignored_reason: str | None


class BrokerMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    external_case_id: UUID
    request_key: str = Field(min_length=8, max_length=120)
    reason: str = Field(min_length=3, max_length=200)


class BrokerUnlinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    request_key: str = Field(min_length=8, max_length=120)
    reason: str = Field(min_length=3, max_length=200)


class BrokerIgnoreRequest(BrokerUnlinkRequest):
    pass
