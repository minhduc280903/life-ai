"""Celery tasks for discovery pipeline execution."""

import time
from datetime import datetime
from typing import Any
from uuid import UUID

from celery import Task

from app.agents.generator_agent import GeneratedMolecule, GeneratorAgent, GeneratorInput
from app.agents.planner_agent import PlannerAgent, PlannerInput
from app.agents.ranker_agent import RankerAgent, RankerInput
from app.core.config import get_settings
from app.core.database import get_sync_session
from app.core.logging import clear_run_context, get_logger, set_run_context
from app.models.molecule import Molecule
from app.models.run import DiscoveryRun, RunStatus
from app.models.trace import AgentTrace
from app.schemas.run_schema import FilterConfig, RunConfig
from app.worker.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


class DiscoveryTask(Task):
    """Base task with error handling and database session management."""

    abstract = True

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Handle task failure by updating run status."""
        run_id = args[0] if args else kwargs.get("run_id")
        if run_id:
            session = get_sync_session()
            try:
                run = session.query(DiscoveryRun).filter(
                    DiscoveryRun.id == UUID(run_id)
                ).first()
                if run:
                    run.status = RunStatus.FAILED
                    run.error_message = str(exc)
                    session.commit()
            finally:
                session.close()

        logger.error(
            "task_failed",
            run_id=run_id,
            error=str(exc),
            task_id=task_id,
        )


def _save_trace(
    session: Any,
    run_id: UUID,
    agent_name: str,
    action: str,
    input_data: dict[str, Any] | None,
    output_data: dict[str, Any] | None,
    duration_ms: float,
) -> None:
    """Persist an agent trace to the database."""
    trace = AgentTrace(
        run_id=run_id,
        agent_name=agent_name,
        action=action,
        input_data=input_data,
        output_data=output_data,
        duration_ms=duration_ms,
    )
    session.add(trace)


def _save_molecules(
    session: Any,
    run_id: UUID,
    molecules: list[GeneratedMolecule],
    round_number: int,
) -> None:
    """Persist generated molecules to the database."""
    for mol in molecules:
        db_mol = Molecule(
            run_id=run_id,
            smiles=mol.smiles,
            is_valid=mol.is_valid,
            round_generated=round_number,
            mw=mol.mw,
            logp=mol.logp,
            hbd=mol.hbd,
            hba=mol.hba,
            tpsa=mol.tpsa,
            rotb=mol.rotb,
            qed=mol.qed,
            violations=mol.violations,
            passed_screening=mol.passed_screening,
            score=mol.score,
        )
        session.add(db_mol)


@celery_app.task(bind=True, base=DiscoveryTask, max_retries=3)
def run_discovery_pipeline(self: Task, run_id: str) -> dict[str, Any]:
    """Execute the full discovery pipeline.

    This task is idempotent: if the run is already COMPLETED or RUNNING,
    it will not re-execute.

    Args:
        run_id: UUID string of the discovery run.

    Returns:
        Dictionary with run results and statistics.
    """
    run_uuid = UUID(run_id)
    set_run_context(run_id)

    session = get_sync_session()
    try:
        # Load run from database
        run = session.query(DiscoveryRun).filter(
            DiscoveryRun.id == run_uuid
        ).first()

        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Idempotency check
        if run.status == RunStatus.COMPLETED:
            logger.info("run_already_completed", run_id=run_id)
            return {"status": "already_completed", "run_id": run_id}

        if run.status == RunStatus.RUNNING:
            logger.info("run_already_running", run_id=run_id)
            return {"status": "already_running", "run_id": run_id}

        # Update status to RUNNING
        run.status = RunStatus.RUNNING
        session.commit()

        # Parse config
        config = RunConfig(**run.config)
        start_time = time.perf_counter()

        # Initialize agents
        planner = PlannerAgent()
        generator = GeneratorAgent()
        ranker = RankerAgent()

        # Step 1: Planner Agent
        logger.info("executing_planner", run_id=run_id)
        planner_start = time.perf_counter()
        planner_input = PlannerInput(run_id=run_uuid, config=config)
        planner_output = planner.execute(planner_input)
        planner_duration = (time.perf_counter() - planner_start) * 1000

        _save_trace(
            session,
            run_uuid,
            planner.name,
            "plan_created",
            {"seeds": config.seeds, "num_rounds": config.num_rounds},
            {
                "validated_seeds": planner_output.validated_seeds,
                "strategy": planner_output.strategy_summary,
            },
            planner_duration,
        )
        session.commit()

        # Step 2: Generator Agent (per round)
        all_molecules: list[GeneratedMolecule] = []
        total_failure_breakdown: dict[str, int] = {}

        seeds = planner_output.validated_seeds
        for round_plan in planner_output.rounds:
            round_num = round_plan.round_number
            logger.info("executing_generator", run_id=run_id, round=round_num)

            # Use seeds from previous round's top candidates for rounds > 1
            if round_num > 1 and all_molecules:
                passed_molecules = [
                    m for m in all_molecules
                    if m.passed_screening and m.score is not None
                ]
                sorted_mols = sorted(
                    passed_molecules,
                    key=lambda m: m.score or 0,
                    reverse=True,
                )
                seeds = [m.smiles for m in sorted_mols[:5]]
                if not seeds:
                    seeds = planner_output.validated_seeds

            generator_start = time.perf_counter()
            generator_input = GeneratorInput(
                run_id=run_uuid,
                round_number=round_num,
                seeds=seeds,
                candidates_target=round_plan.candidates_target,
                filters=planner_output.filters,
            )
            generator_output = generator.execute(generator_input)
            generator_duration = (time.perf_counter() - generator_start) * 1000

            # Collect molecules
            all_molecules.extend(generator_output.molecules)

            # Aggregate failure breakdown
            for key, value in generator_output.failure_breakdown.items():
                total_failure_breakdown[key] = (
                    total_failure_breakdown.get(key, 0) + value
                )

            # Save molecules for this round
            _save_molecules(session, run_uuid, generator_output.molecules, round_num)

            _save_trace(
                session,
                run_uuid,
                generator.name,
                f"generation_round_{round_num}",
                {"seeds": seeds, "target": round_plan.candidates_target},
                {
                    "total": generator_output.total_generated,
                    "valid": generator_output.valid_count,
                    "passed": generator_output.passed_screening_count,
                },
                generator_duration,
            )
            session.commit()

        # Step 3: Ranker Agent
        logger.info("executing_ranker", run_id=run_id)
        ranker_start = time.perf_counter()
        ranker_input = RankerInput(
            run_id=run_uuid,
            molecules=all_molecules,
            top_k=planner_output.top_k,
        )
        ranker_output = ranker.execute(ranker_input)
        ranker_duration = (time.perf_counter() - ranker_start) * 1000

        _save_trace(
            session,
            run_uuid,
            ranker.name,
            "ranking_complete",
            {"total_molecules": len(all_molecules), "top_k": planner_output.top_k},
            {
                "candidates": ranker_output.total_candidates,
                "top_k_returned": ranker_output.top_k_returned,
                "score_range": ranker_output.score_range,
            },
            ranker_duration,
        )

        # Update run with results
        total_duration = (time.perf_counter() - start_time) * 1000
        result_summary = {
            "total_generated": len(all_molecules),
            "total_valid": sum(1 for m in all_molecules if m.is_valid),
            "total_passed_screening": sum(
                1 for m in all_molecules if m.passed_screening
            ),
            "top_candidates_count": ranker_output.top_k_returned,
            "failure_breakdown": total_failure_breakdown,
            "duration_ms": total_duration,
            "top_molecules": [
                {"rank": m.rank, "smiles": m.smiles, "score": m.score}
                for m in ranker_output.ranked_molecules
            ],
        }

        run.status = RunStatus.COMPLETED
        run.result_summary = result_summary
        session.commit()

        logger.info(
            "run_completed",
            run_id=run_id,
            total_generated=result_summary["total_generated"],
            top_k=ranker_output.top_k_returned,
            duration_ms=total_duration,
        )

        return {
            "status": "completed",
            "run_id": run_id,
            "result_summary": result_summary,
        }

    except Exception as e:
        session.rollback()
        # Update run status to FAILED
        try:
            run = session.query(DiscoveryRun).filter(
                DiscoveryRun.id == run_uuid
            ).first()
            if run:
                run.status = RunStatus.FAILED
                run.error_message = str(e)
                session.commit()
        except Exception:
            pass

        logger.error("run_failed", run_id=run_id, error=str(e))
        raise

    finally:
        session.close()
        clear_run_context()
