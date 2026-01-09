"""Pydantic schemas for agent traces."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceCreate(BaseModel):
    """Schema for creating an agent trace entry."""

    run_id: UUID
    agent_name: str
    action: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: float | None = None


class TraceEntry(BaseModel):
    """Response schema for a trace entry."""

    id: int
    run_id: UUID
    timestamp: datetime
    agent_name: str
    action: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    duration_ms: float | None = None

    class Config:
        from_attributes = True


class TraceList(BaseModel):
    """Paginated list of trace entries."""

    traces: list[TraceEntry]
    total: int
    run_id: UUID
