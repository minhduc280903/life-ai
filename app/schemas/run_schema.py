"""Pydantic schemas for discovery runs."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.run import RunStatus


class FilterConfig(BaseModel):
    """Configuration for molecule screening filters."""

    max_mw: float = Field(default=500.0, description="Maximum molecular weight")
    max_logp: float = Field(default=5.0, description="Maximum LogP")
    max_hbd: int = Field(default=5, description="Maximum hydrogen bond donors")
    max_hba: int = Field(default=10, description="Maximum hydrogen bond acceptors")
    max_tpsa: float = Field(default=140.0, description="Maximum TPSA")
    max_rotb: int = Field(default=10, description="Maximum rotatable bonds")
    max_violations: int = Field(default=1, description="Maximum allowed rule violations")


class RunConfig(BaseModel):
    """Configuration for a discovery run."""

    seeds: list[str] = Field(
        ...,
        min_length=1,
        description="List of seed SMILES to start generation from",
    )
    num_rounds: int = Field(default=1, ge=1, le=10, description="Number of generation rounds")
    candidates_per_round: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Number of candidates to generate per round",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of top candidates to return")
    filters: FilterConfig = Field(default_factory=FilterConfig)
    objective: str = Field(
        default="Generate drug-like molecules; maximize QED; minimize violations",
        description="Textual objective for the run",
    )


class RunCreate(BaseModel):
    """Request schema for creating a new run."""

    config: RunConfig


class RunResponse(BaseModel):
    """Response schema for run creation."""

    run_id: UUID
    status: RunStatus
    message: str


class ResultSummary(BaseModel):
    """Summary of run results."""

    total_generated: int = Field(default=0)
    total_valid: int = Field(default=0)
    total_passed_screening: int = Field(default=0)
    top_candidates_count: int = Field(default=0)
    failure_breakdown: dict[str, int] = Field(default_factory=dict)


class RunStatus_(BaseModel):
    """Response schema for run status check."""

    run_id: UUID
    status: RunStatus
    config: RunConfig | None = None
    result_summary: ResultSummary | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
