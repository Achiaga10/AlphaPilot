from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
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


class ResearchTradeEventType(StrEnum):
    OPEN = "OPEN"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"


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
