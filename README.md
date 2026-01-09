# LIFE AI - Agentic Molecular Discovery Pipeline

An asynchronous multi-agent system for CNS drug discovery with emphasis on Blood-Brain Barrier permeability.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI (API Layer)                      │
│  POST /runs  │  GET /runs/{id}  │  GET /molecules  │  GET /traces │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Celery + Redis (Async)                       │
│            run_discovery_pipeline (Idempotent Task)             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ PlannerAgent  │ ───► │GeneratorAgent │ ───► │ RankerAgent   │
│   (Strategy)  │      │  (Mutations)  │      │  (Selection)  │
└───────────────┘      └───────────────┘      └───────────────┘
                               │
                               ▼
                    ┌────────────────────┐
                    │   ChemistryTool    │
                    │   (RDKit Service)  │
                    └────────────────────┘
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)

### Running with Docker

```bash
# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Check logs
docker-compose logs -f
```

### Local Development

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
copy .env.example .env

# Start dependencies (PostgreSQL, Redis)
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload

# Start Celery worker (separate terminal)
celery -A app.worker.celery_app worker --loglevel=info
```

## API Usage

### Create a Discovery Run

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "seeds": ["CCO", "c1ccccc1"],
      "num_rounds": 1,
      "candidates_per_round": 50,
      "top_k": 10,
      "filters": {
        "max_mw": 500,
        "max_logp": 5,
        "max_hbd": 5,
        "max_hba": 10,
        "max_tpsa": 140,
        "max_violations": 1
      }
    }
  }'
```

Response (202 Accepted):
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Discovery run queued for processing"
}
```

### Check Run Status

```bash
curl http://localhost:8000/api/v1/runs/{run_id}
```

### Get Ranked Molecules

```bash
curl http://localhost:8000/api/v1/runs/{run_id}/molecules
```

### Get Agent Traces

```bash
curl http://localhost:8000/api/v1/runs/{run_id}/traces
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_chemistry_tool.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Project Structure

```
life-ai/
├── app/
│   ├── agents/           # Stateless agent implementations
│   │   ├── base_agent.py
│   │   ├── planner_agent.py
│   │   ├── generator_agent.py
│   │   └── ranker_agent.py
│   ├── api/              # FastAPI routes
│   │   └── routes/
│   │       └── runs.py
│   ├── core/             # Core infrastructure
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── models/           # SQLAlchemy models
│   │   ├── run.py
│   │   ├── molecule.py
│   │   └── trace.py
│   ├── schemas/          # Pydantic DTOs
│   ├── services/         # Business logic
│   │   ├── chemistry_tool.py
│   │   ├── mutation_service.py
│   │   └── scoring_service.py
│   ├── worker/           # Celery tasks
│   └── main.py
├── alembic/              # Database migrations
├── tests/                # Unit and integration tests
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Scoring Logic

Molecules are scored using the formula:

```
Score = QED - (0.1 × violations)
```

Where:
- **QED**: Quantitative Estimate of Drug-likeness (0-1)
- **violations**: Count of filter thresholds exceeded

### Filter Thresholds

| Property | Default Max | Description |
|----------|-------------|-------------|
| MW | 500 | Molecular weight |
| LogP | 5 | Lipophilicity |
| HBD | 5 | Hydrogen bond donors |
| HBA | 10 | Hydrogen bond acceptors |
| TPSA | 140 | Topological polar surface area |
| RotB | 10 | Rotatable bonds |

## License

MIT License
