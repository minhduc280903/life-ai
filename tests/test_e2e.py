"""End-to-end test for the LIFE AI pipeline.

This test simulates the full discovery pipeline without requiring
Docker, PostgreSQL, or Redis. It tests the agent chain directly.
"""

import json
from uuid import uuid4

from app.agents.generator_agent import GeneratorAgent, GeneratorInput
from app.agents.planner_agent import PlannerAgent, PlannerInput
from app.agents.ranker_agent import RankerAgent, RankerInput
from app.schemas.run_schema import FilterConfig, RunConfig
from app.services.chemistry_tool import ChemistryTool
from app.services.mutation_service import MutationService


def test_full_pipeline_simulation():
    """Simulate the complete Planner -> Generator -> Ranker pipeline."""
    print("\n" + "=" * 60)
    print("LIFE AI - End-to-End Pipeline Test")
    print("=" * 60)

    run_id = uuid4()

    # Step 1: Define run configuration
    config = RunConfig(
        seeds=["CCO", "c1ccccc1"],  # Ethanol and Benzene
        num_rounds=1,
        candidates_per_round=50,
        top_k=10,
        filters=FilterConfig(
            max_mw=500,
            max_logp=5,
            max_hbd=5,
            max_hba=10,
            max_tpsa=140,
            max_violations=1,
        ),
        objective="Generate drug-like molecules; maximize QED",
    )

    print(f"\n[CONFIG] Run ID: {run_id}")
    print(f"[CONFIG] Seeds: {config.seeds}")
    print(f"[CONFIG] Rounds: {config.num_rounds}")
    print(f"[CONFIG] Candidates/round: {config.candidates_per_round}")
    print(f"[CONFIG] Top-k: {config.top_k}")

    # Step 2: Execute Planner Agent
    print("\n" + "-" * 40)
    print("STEP 1: Planner Agent")
    print("-" * 40)

    planner = PlannerAgent()
    planner_input = PlannerInput(run_id=run_id, config=config)
    planner_output = planner.execute(planner_input)

    print(f"[PLANNER] Validated seeds: {planner_output.validated_seeds}")
    print(f"[PLANNER] Invalid seeds: {planner_output.invalid_seeds}")
    print(f"[PLANNER] Strategy: {planner_output.strategy_summary}")
    print(f"[PLANNER] Rounds planned: {len(planner_output.rounds)}")

    assert len(planner_output.validated_seeds) == 2, "Should validate both seeds"
    assert len(planner_output.rounds) == 1, "Should have 1 round"

    # Step 3: Execute Generator Agent
    print("\n" + "-" * 40)
    print("STEP 2: Generator Agent")
    print("-" * 40)

    generator = GeneratorAgent()
    generator_input = GeneratorInput(
        run_id=run_id,
        round_number=1,
        seeds=planner_output.validated_seeds,
        candidates_target=config.candidates_per_round,
        filters=planner_output.filters,
    )
    generator_output = generator.execute(generator_input)

    print(f"[GENERATOR] Total generated: {generator_output.total_generated}")
    print(f"[GENERATOR] Valid: {generator_output.valid_count}")
    print(f"[GENERATOR] Invalid: {generator_output.invalid_count}")
    print(f"[GENERATOR] Passed screening: {generator_output.passed_screening_count}")
    print(f"[GENERATOR] Failed screening: {generator_output.failed_screening_count}")

    if generator_output.failure_breakdown:
        print(f"[GENERATOR] Failure breakdown: {generator_output.failure_breakdown}")

    assert generator_output.total_generated > 0, "Should generate molecules"

    # Show sample molecules
    valid_mols = [m for m in generator_output.molecules if m.is_valid]
    if valid_mols:
        print(f"\n[GENERATOR] Sample valid molecules:")
        for mol in valid_mols[:3]:
            print(f"  - {mol.smiles}: MW={mol.mw}, LogP={mol.logp}, QED={mol.qed}, Score={mol.score}")

    # Step 4: Execute Ranker Agent
    print("\n" + "-" * 40)
    print("STEP 3: Ranker Agent")
    print("-" * 40)

    ranker = RankerAgent()
    ranker_input = RankerInput(
        run_id=run_id,
        molecules=generator_output.molecules,
        top_k=config.top_k,
    )
    ranker_output = ranker.execute(ranker_input)

    print(f"[RANKER] Total candidates: {ranker_output.total_candidates}")
    print(f"[RANKER] Top-k returned: {ranker_output.top_k_returned}")
    print(f"[RANKER] Score range: {ranker_output.score_range}")

    # Display ranked results
    print(f"\n[RANKER] Top {ranker_output.top_k_returned} Molecules:")
    print("-" * 80)
    print(f"{'Rank':<5} {'SMILES':<30} {'Score':<8} {'QED':<8} {'MW':<8} {'LogP':<8} {'Violations':<10}")
    print("-" * 80)

    for mol in ranker_output.ranked_molecules:
        print(f"{mol.rank:<5} {mol.smiles[:28]:<30} {mol.score:<8.4f} {mol.qed:<8.4f} {mol.mw:<8.2f} {mol.logp:<8.2f} {mol.violations:<10}")

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)

    result_summary = {
        "run_id": str(run_id),
        "total_generated": generator_output.total_generated,
        "total_valid": generator_output.valid_count,
        "total_passed_screening": generator_output.passed_screening_count,
        "top_candidates_count": ranker_output.top_k_returned,
        "failure_breakdown": generator_output.failure_breakdown,
        "top_molecules": [
            {"rank": m.rank, "smiles": m.smiles, "score": m.score}
            for m in ranker_output.ranked_molecules[:5]
        ],
    }

    print(f"Total Generated: {result_summary['total_generated']}")
    print(f"Valid Molecules: {result_summary['total_valid']}")
    print(f"Passed Screening: {result_summary['total_passed_screening']}")
    print(f"Top Candidates: {result_summary['top_candidates_count']}")

    print("\n[SUCCESS] End-to-end pipeline test completed!")
    return result_summary


def test_chemistry_tool_detailed():
    """Test ChemistryTool with various molecules."""
    print("\n" + "=" * 60)
    print("Chemistry Tool Detailed Test")
    print("=" * 60)

    chem = ChemistryTool()
    filters = FilterConfig()

    test_molecules = [
        ("CCO", "Ethanol"),
        ("c1ccccc1", "Benzene"),
        ("CC(=O)Oc1ccccc1C(=O)O", "Aspirin"),
        ("CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "Caffeine"),
        ("invalid_smiles", "Invalid"),
    ]

    print(f"\n{'Name':<15} {'SMILES':<35} {'Valid':<6} {'MW':<8} {'LogP':<8} {'QED':<8} {'Violations':<10}")
    print("-" * 100)

    for smiles, name in test_molecules:
        result = chem.process_smiles(smiles, filters)
        if result["is_valid"]:
            desc = result["descriptors"]
            print(f"{name:<15} {smiles[:33]:<35} {'Yes':<6} {desc.mw:<8.2f} {desc.logp:<8.2f} {desc.qed:<8.4f} {result['violations']:<10}")
        else:
            print(f"{name:<15} {smiles[:33]:<35} {'No':<6} {'-':<8} {'-':<8} {'-':<8} {'-':<10}")

    print("\n[SUCCESS] Chemistry tool test completed!")


def test_mutation_service_detailed():
    """Test MutationService with various transformations."""
    print("\n" + "=" * 60)
    print("Mutation Service Detailed Test")
    print("=" * 60)

    mutation_service = MutationService()

    test_seeds = ["CCF", "c1ccccc1", "CCO"]

    for seed in test_seeds:
        print(f"\n[SEED] {seed}")
        mutations = mutation_service.mutate_molecule(seed, num_mutations=5)

        if mutations:
            for m in mutations:
                print(f"  -> {m.mutated_smiles} ({m.mutation_type})")
        else:
            print("  -> No mutations generated")

    # Test Tanimoto similarity
    print("\n[TANIMOTO TEST]")
    pairs = [
        ("CCO", "CCO"),
        ("CCO", "CCC"),
        ("c1ccccc1", "c1ccc(C)cc1"),
    ]
    for s1, s2 in pairs:
        sim = mutation_service.calculate_tanimoto(s1, s2)
        print(f"  {s1} vs {s2}: {sim:.4f}" if sim else f"  {s1} vs {s2}: N/A")

    print("\n[SUCCESS] Mutation service test completed!")


def test_api_schemas():
    """Test Pydantic schema validation."""
    print("\n" + "=" * 60)
    print("API Schema Validation Test")
    print("=" * 60)

    from app.schemas.run_schema import RunConfig, RunCreate, FilterConfig

    # Valid config
    config = RunConfig(
        seeds=["CCO", "c1ccccc1"],
        num_rounds=2,
        candidates_per_round=100,
        top_k=20,
    )
    print(f"[VALID] RunConfig created: {config.num_rounds} rounds, {config.candidates_per_round} candidates")

    # Test serialization
    config_dict = config.model_dump()
    print(f"[SERIALIZE] Config dict keys: {list(config_dict.keys())}")

    # Test RunCreate
    run_create = RunCreate(config=config)
    print(f"[VALID] RunCreate created with config")

    # Test FilterConfig defaults
    default_filters = FilterConfig()
    print(f"[DEFAULTS] MW<={default_filters.max_mw}, LogP<={default_filters.max_logp}, TPSA<={default_filters.max_tpsa}")

    print("\n[SUCCESS] Schema validation test completed!")


if __name__ == "__main__":
    # Run all tests
    test_chemistry_tool_detailed()
    test_mutation_service_detailed()
    test_api_schemas()
    result = test_full_pipeline_simulation()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
