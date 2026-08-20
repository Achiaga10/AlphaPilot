from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from alphapilot.database.base import Base
from alphapilot.database.mixins import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class IndexConstituent(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """Current membership of a ticker in a market index."""

    __tablename__ = "index_constituents"

    __table_args__ = (
        Index(
            "ix_index_constituents_index_ticker",
            "index_symbol",
            "ticker",
            unique=True,
        ),
        Index(
            "ix_index_constituents_index_active",
            "index_symbol",
            "is_active",
        ),
    )

    index_symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
