from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from alphapilot.database.models.company import Company


class DailyCandle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents one daily OHLCV candle."""

    __tablename__ = "daily_candles"

    __table_args__ = (
        Index("ix_daily_candles_company_date", "company_id", "date", unique=True),
        Index("ix_daily_candles_date", "date"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    open: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    high: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    low: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    close: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    volume: Mapped[int] = mapped_column(
        nullable=False,
    )

    company: Mapped[Company] = relationship(
        back_populates="daily_candles",
    )
