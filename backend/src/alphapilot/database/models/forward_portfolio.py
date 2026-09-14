from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ForwardPortfolioStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"


class ForwardExecutionMode(StrEnum):
    VIRTUAL = "VIRTUAL"


class ForwardBrokerExecutionMode(StrEnum):
    MANUAL_EXTERNAL = "MANUAL_EXTERNAL"


class ForwardCycleStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class ForwardOrderSide(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


class ForwardOrderStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class ForwardPositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ForwardEventType(StrEnum):
    PORTFOLIO_INITIALIZED = "PORTFOLIO_INITIALIZED"
    CYCLE_STARTED = "CYCLE_STARTED"
    CYCLE_COMPLETED = "CYCLE_COMPLETED"
    CYCLE_SKIPPED = "CYCLE_SKIPPED"
    CYCLE_FAILED = "CYCLE_FAILED"
    SIGNAL_APPROVED = "SIGNAL_APPROVED"
    SIGNAL_SKIPPED = "SIGNAL_SKIPPED"
    ENTRY_PLANNED = "ENTRY_PLANNED"
    ENTRY_CANCELLED = "ENTRY_CANCELLED"
    ENTRY_FILLED = "ENTRY_FILLED"
    POSITION_OPENED = "POSITION_OPENED"
    STOP_TRIGGERED = "STOP_TRIGGERED"
    STRATEGY_EXIT_SIGNALLED = "STRATEGY_EXIT_SIGNALLED"
    EXIT_PLANNED = "EXIT_PLANNED"
    EXIT_FILLED = "EXIT_FILLED"
    POSITION_CLOSED = "POSITION_CLOSED"
    PORTFOLIO_PAUSED = "PORTFOLIO_PAUSED"
    PORTFOLIO_RESUMED = "PORTFOLIO_RESUMED"
    DATA_STALE = "DATA_STALE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class ForwardPortfolio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forward_portfolios"
    __table_args__ = (
        CheckConstraint("initial_cash > 0", name="ck_forward_portfolios_initial_cash_positive"),
        CheckConstraint("cash_balance >= 0", name="ck_forward_portfolios_cash_nonnegative"),
        CheckConstraint("equity >= 0", name="ck_forward_portfolios_equity_nonnegative"),
        CheckConstraint("revision >= 0", name="ck_forward_portfolios_revision_nonnegative"),
        Index(
            "uq_forward_portfolios_live_strategy",
            "strategy_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'PAUSED')"),
        ),
    )

    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    broker_execution_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    forward_start_session: Mapped[date] = mapped_column(Date, nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_processed_session: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_successful_cycle: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ForwardCycle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forward_cycles"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "trading_session", name="uq_forward_cycle_session"),
        Index("ix_forward_cycles_portfolio_session", "portfolio_id", "trading_session"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    trading_session: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    audit_facts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ForwardOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forward_orders"
    __table_args__ = (
        CheckConstraint("planned_shares > 0", name="ck_forward_orders_shares_positive"),
        CheckConstraint(
            "approved_allocation >= 0", name="ck_forward_orders_allocation_nonnegative"
        ),
        UniqueConstraint(
            "portfolio_id",
            "company_id",
            "side",
            "source_signal_session",
            name="uq_forward_order_source_signal",
        ),
        Index("ix_forward_orders_portfolio_status", "portfolio_id", "status"),
        Index(
            "uq_forward_pending_entry_company",
            "portfolio_id",
            "company_id",
            unique=True,
            postgresql_where=text("side = 'ENTRY' AND status = 'PENDING'"),
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("forward_positions.id", ondelete="RESTRICT", use_alter=True), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_signal_session: Mapped[date] = mapped_column(Date, nullable=False)
    planned_execution_session: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_execution_session: Mapped[date | None] = mapped_column(Date, nullable=True)
    approved_allocation: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    planned_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    modeled_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    friction_bps: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    friction_dollars: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ranking_score: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    ranking_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loss_control_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    loss_control_boundary: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    loss_control_trigger: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_per_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    planned_risk_dollars: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    planned_risk_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ForwardPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forward_positions"
    __table_args__ = (
        CheckConstraint("shares > 0", name="ck_forward_positions_shares_positive"),
        CheckConstraint("modeled_entry_price > 0", name="ck_forward_positions_entry_positive"),
        Index("ix_forward_positions_portfolio_status", "portfolio_id", "status"),
        Index(
            "uq_forward_open_position_company",
            "portfolio_id",
            "company_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    entry_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_orders.id", ondelete="RESTRICT", use_alter=True), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_session: Mapped[date] = mapped_column(Date, nullable=False)
    entry_session: Mapped[date] = mapped_column(Date, nullable=False)
    raw_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    modeled_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    entry_friction: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    last_mark_session: Mapped[date] = mapped_column(Date, nullable=False)
    last_close: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unrealized_return_pct: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    loss_control_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    loss_control_boundary: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    loss_control_trigger: Mapped[str] = mapped_column(String(100), nullable=False)
    loss_control_source: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    planned_risk_dollars: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    holding_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    holding_calendar_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exit_signal_session: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_session: Mapped[date | None] = mapped_column(Date, nullable=True)
    management_status: Mapped[str] = mapped_column(String(40), nullable=False)


class ForwardTrade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forward_trades"
    __table_args__ = (
        UniqueConstraint("position_id", name="uq_forward_trade_position"),
        Index("ix_forward_trades_portfolio_exit", "portfolio_id", "exit_session"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_positions.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_session: Mapped[date] = mapped_column(Date, nullable=False)
    entry_session: Mapped[date] = mapped_column(Date, nullable=False)
    raw_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    modeled_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    entry_friction: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    approved_allocation: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    loss_control_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    initial_loss_control_boundary: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    loss_control_trigger: Mapped[str] = mapped_column(String(100), nullable=False)
    loss_control_source: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_per_share: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    planned_risk_dollars: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    entry_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    exit_signal_session: Mapped[date] = mapped_column(Date, nullable=False)
    exit_session: Mapped[date] = mapped_column(Date, nullable=False)
    raw_exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    modeled_exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    exit_friction: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    return_pct: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    holding_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    holding_calendar_days: Mapped[int] = mapped_column(Integer, nullable=False)


class ForwardEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "forward_events"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "idempotency_key", name="uq_forward_event_key"),
        Index("ix_forward_events_portfolio_created", "portfolio_id", "created_at"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    trading_session: Mapped[date | None] = mapped_column(Date, nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(10), nullable=True)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False)
    numeric_provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ForwardEquityPoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "forward_equity_points"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "trading_session", name="uq_forward_equity_session"),
        Index("ix_forward_equity_portfolio_session", "portfolio_id", "trading_session"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("forward_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    trading_session: Mapped[date] = mapped_column(Date, nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    positions_market_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    open_position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exposure_pct: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
