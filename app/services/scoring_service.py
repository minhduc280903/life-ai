"""Scoring Service for molecule ranking and prioritization."""

from dataclasses import dataclass

from app.core.config import get_settings
from app.schemas.molecule_schema import MoleculeDescriptors
from app.schemas.run_schema import FilterConfig


@dataclass
class ScoringResult:
    """Result of scoring a molecule."""

    qed: float
    violations: int
    score: float
    passed_screening: bool


class ScoringService:
    """Service for scoring and ranking molecules.

    Implements the scoring formula:
    Score = QED - (penalty_weight * violations)
    """

    def __init__(self, penalty_weight: float | None = None):
        """Initialize scoring service.

        Args:
            penalty_weight: Penalty per violation. Uses config default if None.
        """
        settings = get_settings()
        self.penalty_weight = penalty_weight or settings.scoring_penalty_weight

    def compute_score(self, qed: float, violations: int) -> float:
        """Compute molecule score.

        Args:
            qed: QED score (0-1).
            violations: Number of rule violations.

        Returns:
            Computed score.
        """
        return round(qed - (self.penalty_weight * violations), 4)

    def score_molecule(
        self,
        descriptors: MoleculeDescriptors,
        filters: FilterConfig,
    ) -> ScoringResult:
        """Score a molecule based on its descriptors and filter config.

        Args:
            descriptors: Computed molecular descriptors.
            filters: Filter configuration with thresholds.

        Returns:
            ScoringResult with score and screening status.
        """
        # Count violations
        violations = 0
        if descriptors.mw > filters.max_mw:
            violations += 1
        if descriptors.logp > filters.max_logp:
            violations += 1
        if descriptors.hbd > filters.max_hbd:
            violations += 1
        if descriptors.hba > filters.max_hba:
            violations += 1
        if descriptors.tpsa > filters.max_tpsa:
            violations += 1
        if descriptors.rotb > filters.max_rotb:
            violations += 1

        # Compute score
        score = self.compute_score(descriptors.qed, violations)

        # Check screening
        passed = violations <= filters.max_violations

        return ScoringResult(
            qed=descriptors.qed,
            violations=violations,
            score=score,
            passed_screening=passed,
        )
