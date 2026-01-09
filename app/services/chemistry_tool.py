"""Chemistry Tool service for RDKit operations.

Provides SMILES validation, descriptor calculation, and scoring functionality
with comprehensive error handling for molecular operations.
"""

from dataclasses import dataclass
from typing import Any

from rdkit import Chem
from rdkit.Chem import Descriptors, QED, rdMolDescriptors
from rdkit.Chem.rdchem import Mol

from app.core.logging import get_logger
from app.schemas.molecule_schema import MoleculeDescriptors
from app.schemas.run_schema import FilterConfig

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of SMILES validation."""

    is_valid: bool
    mol: Mol | None
    error: str | None = None


class ChemistryTool:
    """RDKit-based chemistry operations with error handling.

    Provides:
    - SMILES validation and sanitization
    - Molecular descriptor calculation
    - Rule violation counting
    - Scoring function
    """

    def validate_smiles(self, smiles: str) -> ValidationResult:
        """Validate and sanitize a SMILES string.

        Args:
            smiles: SMILES string to validate.

        Returns:
            ValidationResult with is_valid flag, mol object if valid,
            and error message if invalid.
        """
        if not smiles or not isinstance(smiles, str):
            return ValidationResult(is_valid=False, mol=None, error="Empty or invalid SMILES input")

        try:
            mol = Chem.MolFromSmiles(smiles, sanitize=True)
            if mol is None:
                return ValidationResult(
                    is_valid=False,
                    mol=None,
                    error="Failed to parse SMILES",
                )
            return ValidationResult(is_valid=True, mol=mol, error=None)
        except Exception as e:
            error_type = type(e).__name__
            return ValidationResult(
                is_valid=False,
                mol=None,
                error=f"{error_type}: {str(e)}",
            )

    def compute_descriptors(self, mol: Mol) -> MoleculeDescriptors:
        """Compute molecular descriptors using RDKit.

        Args:
            mol: RDKit Mol object.

        Returns:
            MoleculeDescriptors with MW, LogP, HBD, HBA, TPSA, RotB, QED.

        Raises:
            ValueError: If mol is None or invalid.
        """
        if mol is None:
            raise ValueError("Cannot compute descriptors for None molecule")

        try:
            return MoleculeDescriptors(
                mw=round(Descriptors.MolWt(mol), 2),
                logp=round(Descriptors.MolLogP(mol), 2),
                hbd=Descriptors.NumHDonors(mol),
                hba=Descriptors.NumHAcceptors(mol),
                tpsa=round(Descriptors.TPSA(mol), 2),
                rotb=rdMolDescriptors.CalcNumRotatableBonds(mol),
                qed=round(QED.qed(mol), 4),
            )
        except Exception as e:
            logger.error(
                "descriptor_calculation_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def count_violations(
        self,
        descriptors: MoleculeDescriptors,
        filters: FilterConfig,
    ) -> tuple[int, dict[str, bool]]:
        """Count Lipinski-like rule violations based on filter config.

        Args:
            descriptors: Computed molecular descriptors.
            filters: Filter configuration with thresholds.

        Returns:
            Tuple of (violation_count, violation_details).
        """
        violations = {
            "mw_exceeded": descriptors.mw > filters.max_mw,
            "logp_exceeded": descriptors.logp > filters.max_logp,
            "hbd_exceeded": descriptors.hbd > filters.max_hbd,
            "hba_exceeded": descriptors.hba > filters.max_hba,
            "tpsa_exceeded": descriptors.tpsa > filters.max_tpsa,
            "rotb_exceeded": descriptors.rotb > filters.max_rotb,
        }

        count = sum(1 for v in violations.values() if v)
        return count, violations

    def passes_screening(
        self,
        violations: int,
        max_violations: int,
    ) -> bool:
        """Check if molecule passes screening threshold.

        Args:
            violations: Number of rule violations.
            max_violations: Maximum allowed violations.

        Returns:
            True if molecule passes screening.
        """
        return violations <= max_violations

    def compute_score(
        self,
        qed: float,
        violations: int,
        penalty_weight: float = 0.1,
    ) -> float:
        """Compute molecule score using QED and violation penalty.

        Formula: Score = QED - (penalty_weight * violations)

        Args:
            qed: QED score (0-1).
            violations: Number of rule violations.
            penalty_weight: Penalty per violation (default: 0.1).

        Returns:
            Computed score.
        """
        return round(qed - (penalty_weight * violations), 4)

    def process_smiles(
        self,
        smiles: str,
        filters: FilterConfig,
        penalty_weight: float = 0.1,
    ) -> dict[str, Any]:
        """Process a SMILES string through the full chemistry pipeline.

        Args:
            smiles: SMILES string to process.
            filters: Filter configuration.
            penalty_weight: Penalty weight for scoring.

        Returns:
            Dictionary with validation, descriptors, violations, and score.
        """
        result: dict[str, Any] = {
            "smiles": smiles,
            "is_valid": False,
            "error": None,
            "descriptors": None,
            "violations": None,
            "violation_details": None,
            "passed_screening": None,
            "score": None,
        }

        # Validate SMILES
        validation = self.validate_smiles(smiles)
        if not validation.is_valid:
            result["error"] = validation.error
            return result

        result["is_valid"] = True

        # Compute descriptors
        try:
            descriptors = self.compute_descriptors(validation.mol)
            result["descriptors"] = descriptors
        except Exception as e:
            result["is_valid"] = False
            result["error"] = f"Descriptor computation failed: {str(e)}"
            return result

        # Count violations
        violations, violation_details = self.count_violations(descriptors, filters)
        result["violations"] = violations
        result["violation_details"] = violation_details

        # Check screening
        passed = self.passes_screening(violations, filters.max_violations)
        result["passed_screening"] = passed

        # Compute score
        result["score"] = self.compute_score(descriptors.qed, violations, penalty_weight)

        return result
