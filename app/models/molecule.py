"""Molecule model for storing generated molecules and their properties."""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Molecule(Base, UUIDMixin, TimestampMixin):
    """Model for molecules generated during discovery runs."""

    __tablename__ = "molecules"
    __table_args__ = (
        UniqueConstraint("run_id", "smiles", name="uq_run_smiles"),
    )

    # Foreign key to discovery run
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SMILES representation
    smiles: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    # Validation status
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Round in which this molecule was generated
    round_generated: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Molecular descriptors
    mw: Mapped[float | None] = mapped_column(Float, nullable=True)  # Molecular weight
    logp: Mapped[float | None] = mapped_column(Float, nullable=True)  # LogP
    hbd: Mapped[int | None] = mapped_column(Integer, nullable=True)  # H-bond donors
    hba: Mapped[int | None] = mapped_column(Integer, nullable=True)  # H-bond acceptors
    tpsa: Mapped[float | None] = mapped_column(Float, nullable=True)  # TPSA
    rotb: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Rotatable bonds
    qed: Mapped[float | None] = mapped_column(Float, nullable=True)  # QED score

    # Screening results
    violations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_screening: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Final score for ranking
    score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    # Relationship
    run: Mapped["DiscoveryRun"] = relationship(
        "DiscoveryRun",
        back_populates="molecules",
    )


from app.models.run import DiscoveryRun
