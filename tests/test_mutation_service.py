"""Unit tests for MutationService."""

import pytest

from app.services.mutation_service import MutationService


@pytest.fixture
def mutation_service() -> MutationService:
    """Create a MutationService instance."""
    return MutationService()


class TestMoleculeMutation:
    """Tests for molecule mutation functionality."""

    def test_mutate_simple_molecule(self, mutation_service: MutationService) -> None:
        """Simple molecules should produce mutations."""
        results = mutation_service.mutate_molecule("CCO", num_mutations=3)
        
        # Should get some successful mutations
        successful = [r for r in results if r.success]
        assert len(successful) > 0

    def test_mutate_halogenated_molecule(
        self, mutation_service: MutationService
    ) -> None:
        """Halogenated molecules should undergo halogen swaps."""
        # Molecule with fluorine
        results = mutation_service.mutate_molecule("CCF", num_mutations=5)
        
        successful = [r for r in results if r.success]
        # Should get at least one F->Cl mutation
        assert any(r.mutation_type == "F_to_Cl" for r in successful)

    def test_mutate_aromatic(self, mutation_service: MutationService) -> None:
        """Aromatic molecules should undergo aromatic mutations."""
        results = mutation_service.mutate_molecule("c1ccccc1", num_mutations=5)
        
        successful = [r for r in results if r.success]
        assert len(successful) > 0

    def test_mutate_invalid_smiles(self, mutation_service: MutationService) -> None:
        """Invalid SMILES should return empty list."""
        results = mutation_service.mutate_molecule("invalid", num_mutations=5)
        assert results == []


class TestAnalogGeneration:
    """Tests for analog generation."""

    def test_generate_analogs(self, mutation_service: MutationService) -> None:
        """Should generate diverse analogs from seeds."""
        seeds = ["CCO", "c1ccccc1"]
        analogs = mutation_service.generate_analogs(seeds, candidates_per_seed=10)
        
        # Should get some analogs
        assert len(analogs) > 0
        
        # Analogs should be unique
        assert len(analogs) == len(set(analogs))

    def test_generate_from_empty_seeds(
        self, mutation_service: MutationService
    ) -> None:
        """Empty seed list should return empty analogs."""
        analogs = mutation_service.generate_analogs([], candidates_per_seed=10)
        assert analogs == []


class TestTanimotoSimilarity:
    """Tests for Tanimoto similarity calculation."""

    def test_identical_molecules(self, mutation_service: MutationService) -> None:
        """Identical molecules should have Tanimoto = 1.0."""
        similarity = mutation_service.calculate_tanimoto("CCO", "CCO")
        assert similarity == pytest.approx(1.0)

    def test_different_molecules(self, mutation_service: MutationService) -> None:
        """Different molecules should have Tanimoto < 1.0."""
        similarity = mutation_service.calculate_tanimoto("CCO", "c1ccccc1")
        assert similarity is not None
        assert similarity < 1.0

    def test_invalid_smiles(self, mutation_service: MutationService) -> None:
        """Invalid SMILES should return None."""
        similarity = mutation_service.calculate_tanimoto("CCO", "invalid")
        assert similarity is None


class TestDiversityPruning:
    """Tests for diversity pruning."""

    def test_prune_similar_molecules(
        self, mutation_service: MutationService
    ) -> None:
        """Similar molecules should be pruned."""
        # Same molecule repeated
        molecules = ["CCO", "CCO", "CCO"]
        pruned = mutation_service.diversity_prune(molecules, threshold=0.9)
        
        # Should keep only one
        assert len(pruned) == 1

    def test_prune_diverse_molecules(
        self, mutation_service: MutationService
    ) -> None:
        """Diverse molecules should be kept."""
        molecules = ["CCO", "c1ccccc1", "CCCC"]
        pruned = mutation_service.diversity_prune(molecules, threshold=0.7)
        
        # Should keep all or most
        assert len(pruned) >= 2

    def test_prune_empty_list(self, mutation_service: MutationService) -> None:
        """Empty list should return empty."""
        pruned = mutation_service.diversity_prune([], threshold=0.7)
        assert pruned == []
