---
trigger: always_on
---

"Act as a Principal Backend Engineer. Build the LIFE AI assignment with the following strict coding standards:

1. ARCHITECTURE: Use a modular structure: `app/core`, `app/api`, `app/agents`, `app/schemas`, `app/services`, and `app/worker`.
2. ASYNC FIRST: All long-running tasks must be handled by a Celery worker. Use Redis as a broker. The API must return a 202 Accepted with a `run_id` immediately.
3. RDKIT INTEGRATION: Implement a dedicated `ChemistryTool` class. Use `rdkit.Chem.Descriptors` and `rdkit.Chem.QED`. Ensure all molecular operations are wrapped in error handling.
4. SCORING LOGIC: Implement the scoring as a configurable service. Formula: Score = QED - (0.1 * violations). Violations are based on the Lipinski + TPSA criteria provided.
5. CODE STYLE: 
   - No emojis, no fluff in comments. 
   - Use Google-style docstrings.
   - Use Pydantic v2 for all data transfer objects (DTOs).
   - Implement a 'Trace' model that records: timestamp, agent_name, action, and results (JSON).
6. TRACEABILITY: Each 'Run' must have a status: PENDING, RUNNING, COMPLETED, FAILED. Store logs for each step of the agentic loop in the database."