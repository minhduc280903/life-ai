"""Pydantic schemas for molecules."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MoleculeDescriptors(BaseModel):
    """Computed molecular descriptors."""

    mw: float = Field(description="Molecular weight")
    logp: float = Field(description="Octanol-water partition coefficient")
    hbd: int = Field(description="Hydrogen bond donors")
    hba: int = Field(description="Hydrogen bond acceptors")
    tpsa: float = Field(description="Topological polar surface area")
    rotb: int = Field(description="Rotatable bonds")
    qed: float = Field(description="Quantitative estimate of drug-likeness")


class MoleculeCreate(BaseModel):
    """Schema for creating a molecule record."""

    smiles: str
    round_generated: int = 1
    is_valid: bool = True
    descriptors: MoleculeDescriptors | None = None
    violations: int | None = None
    passed_screening: bool | None = None
    score: float | None = None


class MoleculeResponse(BaseModel):
    """Response schema for a molecule."""

    id: UUID
    run_id: UUID
    smiles: str
    is_valid: bool
    round_generated: int
    mw: float | None = None
    logp: float | None = None
    hbd: int | None = None
    hba: int | None = None
    tpsa: float | None = None
    rotb: int | None = None
    qed: float | None = None
    violations: int | None = None
    passed_screening: bool | None = None
    score: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class MoleculeWithRank(MoleculeResponse):
    """Molecule response with rank position."""

    rank: int = Field(description="Rank position in the sorted list")
