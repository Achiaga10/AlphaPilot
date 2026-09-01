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


class ResearchPositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ResearchPositionProvenance(StrEnum):
    PLAN_PROFILE = "PLAN_PROFILE"
    LEGACY_IMPORTED = "LEGACY_IMPORTED"
    MANUAL_EXTERNAL = "MANUAL_EXTERNAL"


class ResearchTradeEventType(StrEnum):
    OPEN = "OPEN"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"


class ResearchReconciliationEventType(StrEnum):
    CASH_DEPOSIT = "CASH_DEPOSIT"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    EXTERNAL_POSITION_IMPORT = "EXTERNAL_POSITION_IMPORT"
    POSITION_RECONCILIATION = "POSITION_RECONCILIATION"


class PaperValidationStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PaperExecutionSource(StrEnum):
    ALPACA_PAPER_MANUAL = "ALPACA_PAPER_MANUAL"


class ResearchPortfolio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_portfolios"
    __table_args__ = (
        CheckConstraint("cash_balance >= 0", name="ck_research_portfolios_cash_nonnegative"),
        CheckConstraint("revision >= 0", name="ck_research_portfolios_revision_nonnegative"),
    )

    stable_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class ResearchPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_positions"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_research_positions_quantity_nonnegative"),
        CheckConstraint(
            "average_entry_cost > 0", name="ck_research_positions_average_cost_positive"
        ),
        CheckConstraint("cost_basis >= 0", name="ck_research_positions_cost_basis_nonnegative"),
        Index("ix_research_positions_portfolio_status", "portfolio_id", "status"),
        Index(
            "uq_research_positions_open_company",
            "portfolio_id",
            "company_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    ticker_at_entry: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_entry_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    entry_trading_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    selection_policy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entry_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entry_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provenance_status: Mapped[str] = mapped_column(String(30), nullable=False)
    modeled_risk_dollars: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    closed_at_trading_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_triggered: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    exit_triggered_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_trigger_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ResearchTradeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_trade_events"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_research_trade_events_quantity_positive"),
        CheckConstraint("execution_price > 0", name="ck_research_trade_events_price_positive"),
        Index("ix_research_trade_events_portfolio_created", "portfolio_id", "created_at"),
        UniqueConstraint("portfolio_id", "action_id", name="uq_research_trade_event_action"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_positions.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    trading_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    cash_effect: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_status: Mapped[str] = mapped_column(String(30), nullable=False)


class PositionMonitoringSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "position_monitoring_snapshots"
    __table_args__ = (
        UniqueConstraint("position_id", "completed_trading_day", name="uq_position_monitoring_day"),
        Index("ix_position_monitoring_portfolio_day", "portfolio_id", "completed_trading_day"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_positions.id", ondelete="CASCADE"), nullable=False
    )
    completed_trading_day: Mapped[date] = mapped_column(Date, nullable=False)
    readiness: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    indicator_facts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    exit_triggered: Mapped[bool] = mapped_column(nullable=False, default=False)


class ResearchReconciliationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_reconciliation_events"
    __table_args__ = (Index("ix_reconciliation_portfolio_created", "portfolio_id", "created_at"),)

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("research_positions.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    portfolio_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    before_facts: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_facts: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PaperValidationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "paper_validation_records"
    __table_args__ = (
        CheckConstraint("actual_quantity > 0", name="ck_paper_validation_quantity_positive"),
        CheckConstraint("actual_entry_price > 0", name="ck_paper_validation_entry_positive"),
        CheckConstraint(
            "actual_exit_quantity IS NULL OR actual_exit_quantity > 0",
            name="ck_paper_validation_exit_quantity_positive",
        ),
        CheckConstraint(
            "actual_exit_price IS NULL OR actual_exit_price > 0",
            name="ck_paper_validation_exit_positive",
        ),
        Index("ix_paper_validation_portfolio_created", "portfolio_id", "created_at"),
        Index("ix_paper_validation_position_created", "position_id", "created_at"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_portfolios.id", ondelete="CASCADE"), nullable=False
    )
    position_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_positions.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_source: Mapped[str] = mapped_column(String(40), nullable=False)
    position_provenance: Mapped[str] = mapped_column(String(30), nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entry_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recommendation_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    actual_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    actual_entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_exit_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    actual_exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    alphapilot_exit_triggered_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    alphapilot_exit_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    alphapilot_trigger_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    entry_evidence_schema_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    exit_evidence_schema_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
