"""API routes for discovery runs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.logging import get_logger
from app.models.molecule import Molecule
from app.models.run import DiscoveryRun, RunStatus
from app.models.trace import AgentTrace
from app.schemas.molecule_schema import MoleculeResponse, MoleculeWithRank
from app.schemas.run_schema import (
    FilterConfig,
    ResultSummary,
    RunConfig,
    RunCreate,
    RunResponse,
    RunStatus_,
)
from app.schemas.trace_schema import TraceEntry, TraceList
from app.worker.tasks import run_discovery_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])

DBSession = Annotated[AsyncSession, Depends(get_async_session)]


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunResponse,
)
async def start_run(
    request: RunCreate,
    db: DBSession,
) -> RunResponse:
    """Start a new discovery run.

    Validates the configuration and queues the run for async processing.
    Returns immediately with a run_id for status polling.

    Args:
        request: RunCreate with configuration.
        db: Database session.

    Returns:
        RunResponse with run_id and status 202 Accepted.
    """
    config = request.config

    # Create run record
    run = DiscoveryRun(
        status=RunStatus.PENDING,
        config=config.model_dump(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Queue the discovery task
    run_discovery_pipeline.delay(str(run.id))

    logger.info(
        "run_created",
        run_id=str(run.id),
        seeds=len(config.seeds),
        rounds=config.num_rounds,
    )

    return RunResponse(
        run_id=run.id,
        status=run.status,
        message="Discovery run queued for processing",
    )


@router.get(
    "/{run_id}",
    response_model=RunStatus_,
)
async def get_run(
    run_id: UUID,
    db: DBSession,
) -> RunStatus_:
    """Get the status and summary of a discovery run.

    Args:
        run_id: UUID of the run.
        db: Database session.

    Returns:
        RunStatus_ with current status and results if completed.
    """
    result = await db.execute(
        select(DiscoveryRun).where(DiscoveryRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    # Parse config and result_summary
    config = RunConfig(**run.config) if run.config else None
    result_summary = (
        ResultSummary(**run.result_summary)
        if run.result_summary
        else None
    )

    return RunStatus_(
        run_id=run.id,
        status=run.status,
        config=config,
        result_summary=result_summary,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get(
    "/{run_id}/molecules",
    response_model=list[MoleculeWithRank],
)
async def get_molecules(
    run_id: UUID,
    db: DBSession,
    passed_only: bool = True,
    limit: int = 50,
) -> list[MoleculeWithRank]:
    """Get molecules for a discovery run, ranked by score.

    Args:
        run_id: UUID of the run.
        db: Database session.
        passed_only: If True, only return molecules that passed screening.
        limit: Maximum number of molecules to return.

    Returns:
        List of ranked molecules with their properties.
    """
    # Verify run exists
    run_result = await db.execute(
        select(DiscoveryRun).where(DiscoveryRun.id == run_id)
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    # Build query
    query = select(Molecule).where(Molecule.run_id == run_id)
    if passed_only:
        query = query.where(
            Molecule.is_valid == True,
            Molecule.passed_screening == True,
        )
    query = query.order_by(Molecule.score.desc().nullslast()).limit(limit)

    result = await db.execute(query)
    molecules = result.scalars().all()

    # Add rank to each molecule
    ranked = [
        MoleculeWithRank(
            **MoleculeResponse.model_validate(mol).model_dump(),
            rank=i + 1,
        )
        for i, mol in enumerate(molecules)
    ]

    return ranked


@router.get(
    "/{run_id}/traces",
    response_model=TraceList,
)
async def get_traces(
    run_id: UUID,
    db: DBSession,
    limit: int = 100,
) -> TraceList:
    """Get agent activity traces for a discovery run.

    Args:
        run_id: UUID of the run.
        db: Database session.
        limit: Maximum number of traces to return.

    Returns:
        TraceList with agent activity timeline.
    """
    # Verify run exists
    run_result = await db.execute(
        select(DiscoveryRun).where(DiscoveryRun.id == run_id)
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )

    # Get traces ordered by timestamp
    query = (
        select(AgentTrace)
        .where(AgentTrace.run_id == run_id)
        .order_by(AgentTrace.timestamp.asc())
        .limit(limit)
    )
    result = await db.execute(query)
    traces = result.scalars().all()

    # Count total traces
    count_query = select(AgentTrace).where(AgentTrace.run_id == run_id)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    return TraceList(
        traces=[TraceEntry.model_validate(t) for t in traces],
        total=total,
        run_id=run_id,
    )
