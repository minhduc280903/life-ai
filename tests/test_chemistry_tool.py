"""Unit tests for ChemistryTool service."""

import pytest

from app.schemas.molecule_schema import MoleculeDescriptors
from app.schemas.run_schema import FilterConfig
from app.services.chemistry_tool import ChemistryTool


@pytest.fixture
def chemistry_tool() -> ChemistryTool:
    """Create a ChemistryTool instance."""
    return ChemistryTool()


@pytest.fixture
def default_filters() -> FilterConfig:
    """Create default filter configuration."""
    return FilterConfig()


class TestSMILESValidation:
    """Tests for SMILES validation functionality."""

    def test_valid_smiles(self, chemistry_tool: ChemistryTool) -> None:
        """Valid SMILES should be accepted."""
        result = chemistry_tool.validate_smiles("CCO")
        assert result.is_valid is True
        assert result.mol is not None
        assert result.error is None

    def test_valid_complex_smiles(self, chemistry_tool: ChemistryTool) -> None:
        """Complex valid SMILES should be accepted."""
        # Benzene
        result = chemistry_tool.validate_smiles("c1ccccc1")
        assert result.is_valid is True

        # Aspirin
        result = chemistry_tool.validate_smiles("CC(=O)Oc1ccccc1C(=O)O")
        assert result.is_valid is True

    def test_invalid_smiles(self, chemistry_tool: ChemistryTool) -> None:
        """Invalid SMILES should be rejected."""
        result = chemistry_tool.validate_smiles("invalid_smiles")
        assert result.is_valid is False
        assert result.mol is None
        assert result.error is not None

    def test_empty_smiles(self, chemistry_tool: ChemistryTool) -> None:
        """Empty SMILES should be rejected."""
        result = chemistry_tool.validate_smiles("")
        assert result.is_valid is False
        assert "Empty" in result.error

    def test_none_smiles(self, chemistry_tool: ChemistryTool) -> None:
        """None SMILES should be rejected."""
        result = chemistry_tool.validate_smiles(None)  # type: ignore
        assert result.is_valid is False


class TestDescriptorCalculation:
    """Tests for molecular descriptor calculation."""

    def test_ethanol_descriptors(self, chemistry_tool: ChemistryTool) -> None:
        """Ethanol descriptors should be calculated correctly."""
        validation = chemistry_tool.validate_smiles("CCO")
        assert validation.is_valid
        
        desc = chemistry_tool.compute_descriptors(validation.mol)
        
        # Ethanol: MW ~46, LogP should be negative
        assert 45 < desc.mw < 47
        assert desc.logp < 1
        assert desc.hbd == 1
        assert desc.hba == 1
        assert desc.tpsa > 0
        assert 0 < desc.qed < 1

    def test_benzene_descriptors(self, chemistry_tool: ChemistryTool) -> None:
        """Benzene descriptors should be calculated correctly."""
        validation = chemistry_tool.validate_smiles("c1ccccc1")
        desc = chemistry_tool.compute_descriptors(validation.mol)
        
        # Benzene: MW ~78, no H-bond donors/acceptors
        assert 77 < desc.mw < 79
        assert desc.hbd == 0
        assert desc.hba == 0
        assert desc.tpsa == 0

    def test_none_mol_raises_error(self, chemistry_tool: ChemistryTool) -> None:
        """Computing descriptors for None should raise ValueError."""
        with pytest.raises(ValueError, match="None molecule"):
            chemistry_tool.compute_descriptors(None)


class TestViolationCounting:
    """Tests for rule violation counting."""

    def test_no_violations(
        self,
        chemistry_tool: ChemistryTool,
        default_filters: FilterConfig,
    ) -> None:
        """Drug-like molecule should have no violations."""
        desc = MoleculeDescriptors(
            mw=300,
            logp=2,
            hbd=2,
            hba=4,
            tpsa=60,
            rotb=5,
            qed=0.8,
        )
        count, details = chemistry_tool.count_violations(desc, default_filters)
        assert count == 0
        assert all(v is False for v in details.values())

    def test_mw_violation(
        self,
        chemistry_tool: ChemistryTool,
        default_filters: FilterConfig,
    ) -> None:
        """High MW should trigger violation."""
        desc = MoleculeDescriptors(
            mw=600,  # Exceeds 500
            logp=2,
            hbd=2,
            hba=4,
            tpsa=60,
            rotb=5,
            qed=0.5,
        )
        count, details = chemistry_tool.count_violations(desc, default_filters)
        assert count == 1
        assert details["mw_exceeded"] is True

    def test_multiple_violations(
        self,
        chemistry_tool: ChemistryTool,
        default_filters: FilterConfig,
    ) -> None:
        """Multiple violations should be counted."""
        desc = MoleculeDescriptors(
            mw=600,
            logp=6,
            hbd=6,
            hba=12,
            tpsa=150,
            rotb=12,
            qed=0.3,
        )
        count, details = chemistry_tool.count_violations(desc, default_filters)
        assert count == 6


class TestScoring:
    """Tests for scoring function."""

    def test_perfect_score(self, chemistry_tool: ChemistryTool) -> None:
        """QED 1.0 with no violations should score 1.0."""
        score = chemistry_tool.compute_score(qed=1.0, violations=0)
        assert score == 1.0

    def test_score_with_violations(self, chemistry_tool: ChemistryTool) -> None:
        """Score should decrease with violations."""
        score = chemistry_tool.compute_score(qed=0.8, violations=2, penalty_weight=0.1)
        assert score == pytest.approx(0.6, rel=0.01)

    def test_custom_penalty(self, chemistry_tool: ChemistryTool) -> None:
        """Custom penalty weight should be applied."""
        score = chemistry_tool.compute_score(qed=0.8, violations=2, penalty_weight=0.2)
        assert score == pytest.approx(0.4, rel=0.01)


class TestFullPipeline:
    """Tests for full process_smiles pipeline."""

    def test_process_valid_drug_like(
        self,
        chemistry_tool: ChemistryTool,
        default_filters: FilterConfig,
    ) -> None:
        """Drug-like molecule should pass screening."""
        result = chemistry_tool.process_smiles("CCO", default_filters)
        
        assert result["is_valid"] is True
        assert result["descriptors"] is not None
        assert result["violations"] is not None
        assert result["passed_screening"] is True
        assert result["score"] is not None

    def test_process_invalid_smiles(
        self,
        chemistry_tool: ChemistryTool,
        default_filters: FilterConfig,
    ) -> None:
        """Invalid SMILES should fail early."""
        result = chemistry_tool.process_smiles("invalid", default_filters)
        
        assert result["is_valid"] is False
        assert result["error"] is not None
        assert result["descriptors"] is None
