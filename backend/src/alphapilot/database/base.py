from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


# Import all models so SQLAlchemy registers them
from alphapilot.database.models.company import Company  # noqa: E402,F401
