"""Generator Agent for molecular mutation and analog production."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent, TimedExecution
from app.core.logging import get_logger
from app.schemas.run_schema import FilterConfig
from app.services.chemistry_tool import ChemistryTool
from app.services.mutation_service import MutationService

logger = get_logger(__name__)


class GeneratorInput(BaseModel):
    """Input for the Generator Agent."""

    run_id: UUID
    round_number: int
    seeds: list[str]
    candidates_target: int
    filters: FilterConfig


class GeneratedMolecule(BaseModel):
    """A generated molecule with its computed properties."""

    smiles: str
    is_valid: bool
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
    error: str | None = None


class GeneratorOutput(BaseModel):
    """Output from the Generator Agent."""

    run_id: UUID
    round_number: int
    total_generated: int
    valid_count: int
    invalid_count: int
    passed_screening_count: int
    failed_screening_count: int
    molecules: list[GeneratedMolecule]
    failure_breakdown: dict[str, int] = Field(default_factory=dict)


class GeneratorAgent(BaseAgent[GeneratorInput, GeneratorOutput]):
    """Agent responsible for generating candidate molecules.

    The Generator:
    1. Mutates seed molecules using SMARTS reactions
    2. Validates generated SMILES
    3. Computes molecular descriptors
    4. Applies diversity pruning
    5. Does NOT rank (that's the Ranker's job)
    """

    name: str = "GeneratorAgent"

    def __init__(self) -> None:
        self.chemistry_tool = ChemistryTool()
        self.mutation_service = MutationService()

    def execute(self, input_data: GeneratorInput) -> GeneratorOutput:
        """Execute generation phase.

        Args:
            input_data: GeneratorInput with seeds and generation parameters.

        Returns:
            GeneratorOutput with generated molecules and statistics.
        """
        with TimedExecution() as timer:
            # Calculate mutations needed per seed
            num_seeds = len(input_data.seeds)
            if num_seeds == 0:
                raise ValueError("No seeds provided for generation")

            mutations_per_seed = max(1, input_data.candidates_target // num_seeds)

            # Generate analog molecules
            all_smiles: set[str] = set()
            for seed in input_data.seeds:
                mutations = self.mutation_service.mutate_molecule(
                    seed,
                    num_mutations=mutations_per_seed,
                )
                for result in mutations:
                    if result.success and result.mutated_smiles:
                        all_smiles.add(result.mutated_smiles)

            # Apply diversity pruning
            diverse_smiles = self.mutation_service.diversity_prune(
                list(all_smiles),
                threshold=0.7,
            )

            # Process each molecule through chemistry pipeline
            molecules: list[GeneratedMolecule] = []
            failure_breakdown: dict[str, int] = {}
            valid_count = 0
            invalid_count = 0
            passed_count = 0
            failed_count = 0

            for smiles in diverse_smiles:
                result = self.chemistry_tool.process_smiles(
                    smiles,
                    input_data.filters,
                )

                if not result["is_valid"]:
                    invalid_count += 1
                    molecules.append(
                        GeneratedMolecule(
                            smiles=smiles,
                            is_valid=False,
                            error=result["error"],
                        )
                    )
                    continue

                valid_count += 1
                desc = result["descriptors"]
                mol = GeneratedMolecule(
                    smiles=smiles,
                    is_valid=True,
                    mw=desc.mw,
                    logp=desc.logp,
                    hbd=desc.hbd,
                    hba=desc.hba,
                    tpsa=desc.tpsa,
                    rotb=desc.rotb,
                    qed=desc.qed,
                    violations=result["violations"],
                    passed_screening=result["passed_screening"],
                    score=result["score"],
                )
                molecules.append(mol)

                if result["passed_screening"]:
                    passed_count += 1
                else:
                    failed_count += 1
                    # Track failure reasons
                    for violation_type, failed in result["violation_details"].items():
                        if failed:
                            failure_breakdown[violation_type] = (
                                failure_breakdown.get(violation_type, 0) + 1
                            )

            self.log_action(
                "generation_complete",
                round=input_data.round_number,
                total=len(molecules),
                valid=valid_count,
                passed=passed_count,
            )

        return GeneratorOutput(
            run_id=input_data.run_id,
            round_number=input_data.round_number,
            total_generated=len(molecules),
            valid_count=valid_count,
            invalid_count=invalid_count,
            passed_screening_count=passed_count,
            failed_screening_count=failed_count,
            molecules=molecules,
            failure_breakdown=failure_breakdown,
        )

    def get_trace_data(
        self,
        input_data: GeneratorInput,
        output_data: GeneratorOutput,
        duration_ms: float,
    ) -> dict[str, Any]:
        """Get trace data for this execution."""
        return {
            "input": {
                "round_number": input_data.round_number,
                "seeds": input_data.seeds,
                "candidates_target": input_data.candidates_target,
            },
            "output": {
                "total_generated": output_data.total_generated,
                "valid_count": output_data.valid_count,
                "passed_screening_count": output_data.passed_screening_count,
                "failure_breakdown": output_data.failure_breakdown,
            },
            "duration_ms": duration_ms,
        }
