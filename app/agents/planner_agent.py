"""Planner Agent for initializing run strategy and orchestrating workflow."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent, TimedExecution
from app.core.logging import get_logger
from app.schemas.run_schema import FilterConfig, RunConfig
from app.services.chemistry_tool import ChemistryTool

logger = get_logger(__name__)


class PlannerInput(BaseModel):
    """Input for the Planner Agent."""

    run_id: UUID
    config: RunConfig


class RoundPlan(BaseModel):
    """Plan for a single round of generation."""

    round_number: int
    seeds: list[str]
    candidates_target: int
    strategy: str = Field(description="Strategy description for this round")


class PlannerOutput(BaseModel):
    """Output from the Planner Agent."""

    run_id: UUID
    validated_seeds: list[str]
    invalid_seeds: list[str]
    rounds: list[RoundPlan]
    total_candidates_target: int
    filters: FilterConfig
    top_k: int
    strategy_summary: str


class PlannerAgent(BaseAgent[PlannerInput, PlannerOutput]):
    """Agent responsible for initializing run plan and strategy.

    The Planner:
    1. Validates seed molecules
    2. Defines round-by-round generation strategy
    3. Sets filtering and ranking parameters
    """

    name: str = "PlannerAgent"

    def __init__(self) -> None:
        self.chemistry_tool = ChemistryTool()

    def execute(self, input_data: PlannerInput) -> PlannerOutput:
        """Execute planning phase.

        Args:
            input_data: PlannerInput with run_id and config.

        Returns:
            PlannerOutput with validated seeds and round plans.
        """
        with TimedExecution() as timer:
            config = input_data.config

            # Validate seed molecules
            validated_seeds: list[str] = []
            invalid_seeds: list[str] = []

            for seed in config.seeds:
                result = self.chemistry_tool.validate_smiles(seed)
                if result.is_valid:
                    validated_seeds.append(seed)
                else:
                    invalid_seeds.append(seed)
                    logger.warning(
                        "invalid_seed",
                        smiles=seed,
                        error=result.error,
                    )

            if not validated_seeds:
                raise ValueError("No valid seed molecules provided")

            # Create round plans
            rounds: list[RoundPlan] = []
            candidates_per_round = config.candidates_per_round

            for round_num in range(1, config.num_rounds + 1):
                # First round: exploratory with original seeds
                # Subsequent rounds: refinement with top candidates from previous round
                if round_num == 1:
                    strategy = "Exploratory generation from original seeds"
                    seeds = validated_seeds
                else:
                    strategy = f"Refinement phase {round_num} using top candidates"
                    seeds = []  # Will be filled with top candidates from previous round

                rounds.append(
                    RoundPlan(
                        round_number=round_num,
                        seeds=seeds,
                        candidates_target=candidates_per_round,
                        strategy=strategy,
                    )
                )

            total_candidates = config.num_rounds * candidates_per_round

            strategy_summary = (
                f"Plan: {config.num_rounds} round(s), "
                f"{candidates_per_round} candidates/round, "
                f"top_k={config.top_k}, "
                f"max_violations={config.filters.max_violations}"
            )

            self.log_action(
                "plan_created",
                validated_seeds=len(validated_seeds),
                invalid_seeds=len(invalid_seeds),
                rounds=config.num_rounds,
                total_candidates=total_candidates,
            )

        return PlannerOutput(
            run_id=input_data.run_id,
            validated_seeds=validated_seeds,
            invalid_seeds=invalid_seeds,
            rounds=rounds,
            total_candidates_target=total_candidates,
            filters=config.filters,
            top_k=config.top_k,
            strategy_summary=strategy_summary,
        )

    def get_trace_data(
        self,
        input_data: PlannerInput,
        output_data: PlannerOutput,
        duration_ms: float,
    ) -> dict[str, Any]:
        """Get trace data for this execution."""
        return {
            "input": {
                "seeds": input_data.config.seeds,
                "num_rounds": input_data.config.num_rounds,
                "candidates_per_round": input_data.config.candidates_per_round,
            },
            "output": {
                "validated_seeds": output_data.validated_seeds,
                "invalid_seeds": output_data.invalid_seeds,
                "strategy_summary": output_data.strategy_summary,
            },
            "duration_ms": duration_ms,
        }
