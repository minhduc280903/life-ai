"""Mutation Service for molecular structure modifications.

Implements skeletal editing via Reaction SMARTS to generate molecular analogs
through atom/functional group substitutions.
"""

import random
from dataclasses import dataclass, field

from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs
from rdkit.Chem.rdchem import Mol

from app.core.logging import get_logger

logger = get_logger(__name__)


# Reaction SMARTS for molecular mutations
MUTATION_REACTIONS: list[tuple[str, str]] = [
    # Halogen substitutions
    ("[#6:1][F]>>[#6:1][Cl]", "F_to_Cl"),
    ("[#6:1][Cl]>>[#6:1][F]", "Cl_to_F"),
    ("[#6:1][Br]>>[#6:1][Cl]", "Br_to_Cl"),
    ("[#6:1][Cl]>>[#6:1][Br]", "Cl_to_Br"),

    # Methyl group modifications
    ("[c:1][H]>>[c:1]C", "aromatic_methylation"),
    ("[C:1][CH3]>>[C:1][H]", "demethylation"),

    # Hydroxyl modifications
    ("[#6:1][OH]>>[#6:1][OCH3]", "OH_to_OCH3"),
    ("[#6:1][OCH3]>>[#6:1][OH]", "OCH3_to_OH"),

    # Amino modifications
    ("[#6:1][NH2]>>[#6:1][NHCH3]", "NH2_to_NHCH3"),
    ("[#6:1][NHCH3]>>[#6:1][NH2]", "NHCH3_to_NH2"),

    # Ring modifications
    ("[c:1]1[c:2][c:3][c:4][c:5][c:6]1>>[c:1]1[c:2][n:3][c:4][c:5][c:6]1", "benzene_to_pyridine"),
]


@dataclass
class MutationResult:
    """Result of a mutation operation."""

    success: bool
    original_smiles: str
    mutated_smiles: str | None = None
    mutation_type: str | None = None
    error: str | None = None


@dataclass
class MutationService:
    """Service for generating molecular analogs through mutations.

    Uses RDKit Reaction SMARTS to apply structural transformations
    to seed molecules, generating diverse analog libraries.
    """

    reactions: list[tuple[str, str]] = field(default_factory=lambda: MUTATION_REACTIONS.copy())
    max_attempts_per_mutation: int = 10

    def _apply_reaction(
        self,
        mol: Mol,
        reaction_smarts: str,
        reaction_name: str,
    ) -> MutationResult:
        """Apply a single reaction SMARTS to a molecule.

        Args:
            mol: RDKit Mol object.
            reaction_smarts: Reaction SMARTS string.
            reaction_name: Human-readable reaction name.

        Returns:
            MutationResult with success status and mutated SMILES.
        """
        original_smiles = Chem.MolToSmiles(mol)

        try:
            rxn = AllChem.ReactionFromSmarts(reaction_smarts)
            products = rxn.RunReactants((mol,))

            if not products:
                return MutationResult(
                    success=False,
                    original_smiles=original_smiles,
                    error="No products generated",
                )

            # Take first product from first product set
            product_mol = products[0][0]

            # Sanitize the product
            try:
                Chem.SanitizeMol(product_mol)
            except Exception as e:
                return MutationResult(
                    success=False,
                    original_smiles=original_smiles,
                    error=f"Sanitization failed: {str(e)}",
                )

            mutated_smiles = Chem.MolToSmiles(product_mol)

            # Check if mutation actually changed the molecule
            if mutated_smiles == original_smiles:
                return MutationResult(
                    success=False,
                    original_smiles=original_smiles,
                    error="Mutation produced identical molecule",
                )

            return MutationResult(
                success=True,
                original_smiles=original_smiles,
                mutated_smiles=mutated_smiles,
                mutation_type=reaction_name,
            )

        except Exception as e:
            return MutationResult(
                success=False,
                original_smiles=original_smiles,
                error=f"{type(e).__name__}: {str(e)}",
            )

    def mutate_molecule(
        self,
        smiles: str,
        num_mutations: int = 5,
    ) -> list[MutationResult]:
        """Generate multiple mutations of a molecule.

        Args:
            smiles: SMILES string of the seed molecule.
            num_mutations: Target number of successful mutations.

        Returns:
            List of successful MutationResults.
        """
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            logger.warning("invalid_seed_smiles", smiles=smiles)
            return []

        results: list[MutationResult] = []
        seen_smiles: set[str] = {smiles}
        attempts = 0

        while len(results) < num_mutations and attempts < self.max_attempts_per_mutation * num_mutations:
            attempts += 1

            # Randomly select a reaction
            reaction_smarts, reaction_name = random.choice(self.reactions)

            result = self._apply_reaction(mol, reaction_smarts, reaction_name)

            if result.success and result.mutated_smiles not in seen_smiles:
                results.append(result)
                seen_smiles.add(result.mutated_smiles)

        return results

    def generate_analogs(
        self,
        seed_smiles_list: list[str],
        candidates_per_seed: int = 25,
    ) -> list[str]:
        """Generate analog molecules from a list of seeds.

        Args:
            seed_smiles_list: List of seed SMILES strings.
            candidates_per_seed: Number of analogs to attempt per seed.

        Returns:
            List of unique mutated SMILES strings.
        """
        all_analogs: set[str] = set()

        for seed in seed_smiles_list:
            mutations = self.mutate_molecule(seed, candidates_per_seed)
            for result in mutations:
                if result.success and result.mutated_smiles:
                    all_analogs.add(result.mutated_smiles)

        return list(all_analogs)

    def calculate_tanimoto(self, smiles1: str, smiles2: str, radius: int = 2) -> float | None:
        """Calculate Tanimoto similarity between two molecules.

        Uses Morgan fingerprints (ECFP-like) for comparison.

        Args:
            smiles1: First SMILES string.
            smiles2: Second SMILES string.
            radius: Fingerprint radius (default: 2 for ECFP4-like).

        Returns:
            Tanimoto coefficient (0-1) or None if calculation fails.
        """
        mol1 = Chem.MolFromSmiles(smiles1)
        mol2 = Chem.MolFromSmiles(smiles2)

        if mol1 is None or mol2 is None:
            return None

        try:
            fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, radius, nBits=2048)
            fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, radius, nBits=2048)
            return DataStructs.TanimotoSimilarity(fp1, fp2)
        except Exception as e:
            logger.warning("tanimoto_calculation_failed", error=str(e))
            return None

    def diversity_prune(
        self,
        smiles_list: list[str],
        threshold: float = 0.7,
    ) -> list[str]:
        """Prune a list of SMILES to ensure structural diversity.

        Removes molecules that are too similar (Tanimoto >= threshold)
        to previously selected molecules.

        Args:
            smiles_list: List of SMILES strings.
            threshold: Maximum Tanimoto similarity allowed (default: 0.7).

        Returns:
            Pruned list of diverse SMILES.
        """
        if not smiles_list:
            return []

        diverse: list[str] = [smiles_list[0]]

        for candidate in smiles_list[1:]:
            is_diverse = True
            for selected in diverse:
                similarity = self.calculate_tanimoto(candidate, selected)
                if similarity is not None and similarity >= threshold:
                    is_diverse = False
                    break

            if is_diverse:
                diverse.append(candidate)

        return diverse
