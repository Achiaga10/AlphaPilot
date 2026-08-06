from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alphapilot.database.base import Base
from alphapilot.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from .daily_candle import DailyCandle
    # from .news import News


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    __table_args__ = (
        Index("ix_companies_ticker", "ticker"),
        Index("ix_companies_exchange", "exchange"),
        Index("ix_companies_sector", "sector"),
    )

    ticker: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    exchange: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    sector: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    market_cap: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    daily_candles: Mapped[list["DailyCandle"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )

    # news: Mapped[list["News"]] = relationship(
    #     back_populates="company",
    #     cascade="all, delete-orphan",
    # )
