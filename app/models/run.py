"""DiscoveryRun model for tracking discovery pipeline executions."""

import enum
from typing import Any

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class RunStatus(str, enum.Enum):
    """Status of a discovery run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DiscoveryRun(Base, UUIDMixin, TimestampMixin):
    """Model for discovery pipeline runs."""

    __tablename__ = "discovery_runs"

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus),
        default=RunStatus.PENDING,
        nullable=False,
    )

    # Run configuration stored as JSONB for flexibility
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Summary of results after completion
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Error message if run failed
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # Relationships
    molecules: Mapped[list["Molecule"]] = relationship(
        "Molecule",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    traces: Mapped[list["AgentTrace"]] = relationship(
        "AgentTrace",
        back_populates="run",
        cascade="all, delete-orphan",
    )


# Import for type hints (avoid circular imports)
from app.models.molecule import Molecule
from app.models.trace import AgentTrace
