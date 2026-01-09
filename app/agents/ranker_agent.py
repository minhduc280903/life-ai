"""Ranker Agent for lead prioritization and top-k selection."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent, TimedExecution
from app.agents.generator_agent import GeneratedMolecule
from app.core.logging import get_logger

logger = get_logger(__name__)


class RankerInput(BaseModel):
    """Input for the Ranker Agent."""

    run_id: UUID
    molecules: list[GeneratedMolecule]
    top_k: int


class RankedMolecule(BaseModel):
    """A ranked molecule with its position."""

    rank: int
    smiles: str
    score: float
    qed: float
    violations: int
    mw: float
    logp: float
    hbd: int
    hba: int
    tpsa: float
    rotb: int


class RankerOutput(BaseModel):
    """Output from the Ranker Agent."""

    run_id: UUID
    total_candidates: int
    top_k_requested: int
    top_k_returned: int
    ranked_molecules: list[RankedMolecule]
    score_range: tuple[float, float] = Field(description="(min_score, max_score)")


class RankerAgent(BaseAgent[RankerInput, RankerOutput]):
    """Agent responsible for ranking and selecting top candidates.

    The Ranker:
    1. Filters to valid, screening-passed molecules
    2. Sorts by score descending
    3. Selects top_k candidates
    4. Returns ranked list for export
    """

    name: str = "RankerAgent"

    def execute(self, input_data: RankerInput) -> RankerOutput:
        """Execute ranking phase.

        Args:
            input_data: RankerInput with molecules and top_k parameter.

        Returns:
            RankerOutput with ranked top-k molecules.
        """
        with TimedExecution() as timer:
            # Filter to valid, screening-passed molecules with scores
            candidates = [
                mol for mol in input_data.molecules
                if mol.is_valid
                and mol.passed_screening
                and mol.score is not None
            ]

            if not candidates:
                self.log_action(
                    "no_candidates",
                    total_input=len(input_data.molecules),
                )
                return RankerOutput(
                    run_id=input_data.run_id,
                    total_candidates=0,
                    top_k_requested=input_data.top_k,
                    top_k_returned=0,
                    ranked_molecules=[],
                    score_range=(0.0, 0.0),
                )

            # Sort by score descending
            sorted_candidates = sorted(
                candidates,
                key=lambda m: m.score or 0.0,
                reverse=True,
            )

            # Select top_k
            top_k_candidates = sorted_candidates[: input_data.top_k]

            # Convert to ranked molecules
            ranked_molecules: list[RankedMolecule] = []
            for i, mol in enumerate(top_k_candidates, start=1):
                ranked_molecules.append(
                    RankedMolecule(
                        rank=i,
                        smiles=mol.smiles,
                        score=mol.score or 0.0,
                        qed=mol.qed or 0.0,
                        violations=mol.violations or 0,
                        mw=mol.mw or 0.0,
                        logp=mol.logp or 0.0,
                        hbd=mol.hbd or 0,
                        hba=mol.hba or 0,
                        tpsa=mol.tpsa or 0.0,
                        rotb=mol.rotb or 0,
                    )
                )

            # Calculate score range
            all_scores = [m.score or 0.0 for m in candidates]
            score_range = (min(all_scores), max(all_scores))

            self.log_action(
                "ranking_complete",
                total_candidates=len(candidates),
                top_k_returned=len(ranked_molecules),
                best_score=score_range[1],
            )

        return RankerOutput(
            run_id=input_data.run_id,
            total_candidates=len(candidates),
            top_k_requested=input_data.top_k,
            top_k_returned=len(ranked_molecules),
            ranked_molecules=ranked_molecules,
            score_range=score_range,
        )

    def get_trace_data(
        self,
        input_data: RankerInput,
        output_data: RankerOutput,
        duration_ms: float,
    ) -> dict[str, Any]:
        """Get trace data for this execution."""
        return {
            "input": {
                "total_molecules": len(input_data.molecules),
                "top_k": input_data.top_k,
            },
            "output": {
                "total_candidates": output_data.total_candidates,
                "top_k_returned": output_data.top_k_returned,
                "score_range": output_data.score_range,
                "top_molecules": [
                    {"rank": m.rank, "smiles": m.smiles, "score": m.score}
                    for m in output_data.ranked_molecules[:5]
                ],
            },
            "duration_ms": duration_ms,
        }
