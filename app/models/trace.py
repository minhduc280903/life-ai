"""AgentTrace model for structured logging of agent activities."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AgentTrace(Base):
    """Model for recording agent activity traces.

    Uses BigSerial for high-volume ingestion during extensive search campaigns.
    """

    __tablename__ = "agent_traces"

    # BigSerial primary key for high volume
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign key to discovery run
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamp of the trace
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Agent identification
    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Action performed
    action: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Input data to the agent/tool
    input_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Output/result data from the agent/tool
    output_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Duration of the operation in milliseconds
    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Relationship
    run: Mapped["DiscoveryRun"] = relationship(
        "DiscoveryRun",
        back_populates="traces",
    )


from app.models.run import DiscoveryRun
