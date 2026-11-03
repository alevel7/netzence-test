from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    # Generate __tablename__ automatically from lowercase class name if not set
    @classmethod
    def __tablename_computed__(cls) -> str:
        return cls.__name__.lower() + "s"


class TimestampMixin:
    """Mixin adding created_at and updated_at timezone-aware datetime fields."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

