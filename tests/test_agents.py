"""Unit tests for agents."""

from uuid import uuid4

import pytest

from app.agents.generator_agent import GeneratedMolecule, GeneratorAgent, GeneratorInput
from app.agents.planner_agent import PlannerAgent, PlannerInput
from app.agents.ranker_agent import RankerAgent, RankerInput
from app.schemas.run_schema import FilterConfig, RunConfig


@pytest.fixture
def run_id():
    """Generate a test run ID."""
    return uuid4()


@pytest.fixture
def default_config() -> RunConfig:
    """Create default run configuration."""
    return RunConfig(
        seeds=["CCO", "c1ccccc1"],
        num_rounds=1,
        candidates_per_round=10,
        top_k=5,
    )


class TestPlannerAgent:
    """Tests for PlannerAgent."""

    def test_execute_with_valid_seeds(
        self,
        run_id,
        default_config: RunConfig,
    ) -> None:
        """Planner should validate seeds and create plan."""
        agent = PlannerAgent()
        input_data = PlannerInput(run_id=run_id, config=default_config)
        
        output = agent.execute(input_data)
        
        assert output.run_id == run_id
        assert len(output.validated_seeds) == 2
        assert len(output.invalid_seeds) == 0
        assert len(output.rounds) == 1

    def test_execute_with_invalid_seeds(self, run_id) -> None:
        """Planner should filter out invalid seeds."""
        config = RunConfig(
            seeds=["CCO", "invalid_smiles", "c1ccccc1"],
            num_rounds=1,
            candidates_per_round=10,
        )
        agent = PlannerAgent()
        input_data = PlannerInput(run_id=run_id, config=config)
        
        output = agent.execute(input_data)
        
        assert len(output.validated_seeds) == 2
        assert len(output.invalid_seeds) == 1
        assert "invalid_smiles" in output.invalid_seeds

    def test_execute_with_all_invalid_seeds(self, run_id) -> None:
        """Planner should raise error if all seeds invalid."""
        config = RunConfig(
            seeds=["invalid1", "invalid2"],
            num_rounds=1,
        )
        agent = PlannerAgent()
        input_data = PlannerInput(run_id=run_id, config=config)
        
        with pytest.raises(ValueError, match="No valid seed"):
            agent.execute(input_data)


class TestGeneratorAgent:
    """Tests for GeneratorAgent."""

    def test_execute_generates_molecules(self, run_id) -> None:
        """Generator should produce molecules from seeds."""
        agent = GeneratorAgent()
        input_data = GeneratorInput(
            run_id=run_id,
            round_number=1,
            seeds=["CCO", "c1ccccc1"],
            candidates_target=10,
            filters=FilterConfig(),
        )
        
        output = agent.execute(input_data)
        
        assert output.run_id == run_id
        assert output.round_number == 1
        assert output.total_generated > 0
        assert len(output.molecules) > 0

    def test_execute_computes_descriptors(self, run_id) -> None:
        """Generator should compute descriptors for valid molecules."""
        agent = GeneratorAgent()
        input_data = GeneratorInput(
            run_id=run_id,
            round_number=1,
            seeds=["CCO"],
            candidates_target=5,
            filters=FilterConfig(),
        )
        
        output = agent.execute(input_data)
        
        valid_molecules = [m for m in output.molecules if m.is_valid]
        for mol in valid_molecules[:3]:
            assert mol.mw is not None
            assert mol.logp is not None
            assert mol.qed is not None

    def test_execute_with_no_seeds_raises(self, run_id) -> None:
        """Generator should raise error with empty seeds."""
        agent = GeneratorAgent()
        input_data = GeneratorInput(
            run_id=run_id,
            round_number=1,
            seeds=[],
            candidates_target=10,
            filters=FilterConfig(),
        )
        
        with pytest.raises(ValueError, match="No seeds"):
            agent.execute(input_data)


class TestRankerAgent:
    """Tests for RankerAgent."""

    def test_execute_ranks_by_score(self, run_id) -> None:
        """Ranker should sort molecules by score descending."""
        molecules = [
            GeneratedMolecule(
                smiles="CCO",
                is_valid=True,
                passed_screening=True,
                score=0.5,
                qed=0.6,
                violations=1,
                mw=46,
                logp=-0.2,
                hbd=1,
                hba=1,
                tpsa=20,
                rotb=0,
            ),
            GeneratedMolecule(
                smiles="c1ccccc1",
                is_valid=True,
                passed_screening=True,
                score=0.8,
                qed=0.8,
                violations=0,
                mw=78,
                logp=2.0,
                hbd=0,
                hba=0,
                tpsa=0,
                rotb=0,
            ),
        ]
        
        agent = RankerAgent()
        input_data = RankerInput(
            run_id=run_id,
            molecules=molecules,
            top_k=5,
        )
        
        output = agent.execute(input_data)
        
        assert output.total_candidates == 2
        assert output.top_k_returned == 2
        # Best score should be first
        assert output.ranked_molecules[0].score == 0.8
        assert output.ranked_molecules[1].score == 0.5

    def test_execute_filters_invalid(self, run_id) -> None:
        """Ranker should filter out invalid molecules."""
        molecules = [
            GeneratedMolecule(
                smiles="CCO", is_valid=False, passed_screening=False, score=None
            ),
            GeneratedMolecule(
                smiles="c1ccccc1",
                is_valid=True,
                passed_screening=True,
                score=0.8,
                qed=0.8,
                violations=0,
                mw=78,
                logp=2.0,
                hbd=0,
                hba=0,
                tpsa=0,
                rotb=0,
            ),
        ]
        
        agent = RankerAgent()
        input_data = RankerInput(run_id=run_id, molecules=molecules, top_k=5)
        
        output = agent.execute(input_data)
        
        assert output.total_candidates == 1
        assert output.top_k_returned == 1

    def test_execute_empty_molecules(self, run_id) -> None:
        """Ranker should handle empty molecule list."""
        agent = RankerAgent()
        input_data = RankerInput(run_id=run_id, molecules=[], top_k=5)
        
        output = agent.execute(input_data)
        
        assert output.total_candidates == 0
        assert output.top_k_returned == 0
        assert output.ranked_molecules == []
