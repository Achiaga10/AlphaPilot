from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LiveMarketSnapshotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    company_id: UUID
    session_date: date
    last_price: Decimal
    session_open: Decimal | None
    session_high: Decimal | None
    session_low: Decimal | None
    volume: int | None
    previous_completed_close: Decimal | None
    quote_timestamp: datetime
    received_at: datetime
    provider: str
    feed: str
    freshness: str
    age_seconds: int
    coverage_note: str


class LivePositionIntelligenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: UUID
    ticker: str
    company_name: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    quantity: int
    average_cost: Decimal
    completed_session: date | None
    latest_completed_close: Decimal | None
    live: LiveMarketSnapshotSchema | None
    today_change_dollars: Decimal | None
    today_change_pct: Decimal | None
    completed_ema20: Decimal | None
    provisional_ema20: Decimal | None
    completed_ema50: Decimal | None
    provisional_ema50: Decimal | None
    completed_sma150: Decimal | None
    provisional_sma150: Decimal | None
    completed_atr14: Decimal | None
    provisional_atr14: Decimal | None
    distance_to_ema20_dollars: Decimal | None
    distance_to_ema20_pct: Decimal | None
    distance_to_ema50_dollars: Decimal | None
    distance_to_ema50_pct: Decimal | None
    distance_to_sma150_dollars: Decimal | None
    distance_to_sma150_pct: Decimal | None
    confirmed_status: str | None
    confirmed_reason: str
    live_status: str
    live_reason: str
    projected_signal_if_closed_now: str | None
    projected_reason: str | None
    projection_is_official: bool
    confirmed_sell_required: bool
    loss_control_policy: str
    loss_control_boundary: Decimal | None
    loss_control_trigger: str | None
    broker_stop_order: bool


class PortfolioLiveBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    portfolio_revision: int
    completed_session: date | None
    live_refresh_timestamp: datetime
    provider: str
    feed: str
    overall_readiness: str
    positions: tuple[LivePositionIntelligenceSchema, ...]
    partial_failures: tuple[str, ...]
    requested_tickers: int
    successful_tickers: int
