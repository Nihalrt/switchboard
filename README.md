# Switchboard

Switchboard is a feature-flag monitoring prototype that routes devices between
legacy and new code paths, measures failures, and investigates both individual
flag regressions and cross-flag interactions.

The project addresses a common rollout problem: a new feature may fail on its
own, or two individually acceptable features may fail only when the same device
receives both. Switchboard separates those investigations into two agents:

- **Agent 1** compares one flag's new pipeline with its legacy pipeline. It can
  leave a healthy rollout unchanged, roll back a clear regression, or create an
  escalation when the evidence needs cross-flag analysis.
- **Agent 2** reads unresolved escalations, evaluates every flag pair, compares
  devices receiving both new pipelines with devices receiving exactly one, and
  records statistically significant interaction findings.

## Architecture

```text
Manager API ──writes rollout──> PostgreSQL
     │
     └────────updates──────────> Redis
                                  │
Device ──decision request──> Go relay
                                  │
                                  └── new or legacy decision

Synthetic routing outcomes ──> routing_events
                                      │
                                      ▼
                                  Agent 1
                                      │
                             unresolved escalations
                                      │
                                      ▼
                                  Agent 2
                                      │
                             interaction_findings
```

The current version is a local prototype. Manual scenario scripts generate
completed routing outcomes; live routing-event and outcome ingestion is listed
under Future enhancements.

## Technology

- FastAPI and SQLAlchemy for flag management
- PostgreSQL for flags, routing events, escalations, and findings
- Redis for low-latency rollout lookup
- Go for deterministic device routing
- SciPy chi-square tests for statistical filtering
- Gemini for constrained operational recommendations
- Python `unittest` with in-memory SQLite for isolated workflow tests

## Repository layout

```text
manager/   FastAPI flag-management service
relay/     Go service that assigns deterministic rollout buckets
agents/    Agent 1, Agent 2, database models, and tests
```

## Local setup

### 1. Start PostgreSQL and Redis

For a new environment:

```bash
docker compose up -d --wait
```

If PostgreSQL and Redis are already running separately on ports `5432` and
`6379`, use those instances instead of starting Compose.

### 2. Install Python dependencies

Manager environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r manager/requirements.txt
```

Agent environment:

```bash
python3 -m venv agents/.venv
agents/.venv/bin/pip install -r agents/requirements.txt
```

Copy the example configuration and add a Gemini API key:

```bash
cp .env.example agents/.env
```

### 3. Create database tables

```bash
DATABASE_URL=postgresql://switchboard:switchboard@127.0.0.1:5432/switchboard \
.venv/bin/python -c 'from manager.app.database import engine; from manager.app.models import Base; Base.metadata.create_all(bind=engine)'
```

```bash
cd agents
DATABASE_URL=postgresql://switchboard:switchboard@127.0.0.1:5432/switchboard \
.venv/bin/python -c 'from db import engine; from models import Base; Base.metadata.create_all(bind=engine)'
cd ..
```

### 4. Start the Manager

```bash
DATABASE_URL=postgresql://switchboard:switchboard@127.0.0.1:5432/switchboard \
REDIS_ADDR=127.0.0.1:6379 \
.venv/bin/uvicorn manager.app.main:app --port 8001
```

Interactive API documentation is available at
`http://127.0.0.1:8001/docs`.

### 5. Start the relay

```bash
cd relay
REDIS_ADDR=127.0.0.1:6379 go run ./cmd/relay
```

The relay listens on `http://127.0.0.1:8080/decide`.

## Tests

### Automated agent tests

These tests use in-memory SQLite and mocked Gemini responses. They do not
modify PostgreSQL or make external model calls.

```bash
cd agents
GEMINI_API_KEY=test-key \
DATABASE_URL=sqlite:///:memory: \
.venv/bin/python -m unittest -v test_agent_2.py
```

The suite covers:

- overlap and comparison-group construction;
- sample-size and failure-count behavior;
- chi-square significance;
- constrained Gemini verdict parsing;
- finding persistence and escalation resolution;
- the complete Agent 1 to Agent 2 handoff.

### Relay tests

```bash
cd relay
go test ./...
```

### Manual Agent 1 scenario

With PostgreSQL, Redis, the Manager, and a valid Gemini key running:

```bash
cd agents
DATABASE_URL=postgresql://switchboard:switchboard@127.0.0.1:5432/switchboard \
MANAGER_URL=http://127.0.0.1:8001 \
.venv/bin/python manual_test_agent_1.py
```

The script demonstrates healthy, escalation, and rollback scenarios.

### Manual Agent 2 scenario

With PostgreSQL and a valid Gemini key running:

```bash
cd agents
DATABASE_URL=postgresql://switchboard:switchboard@127.0.0.1:5432/switchboard \
.venv/bin/python manual_test_agent_2.py
```

The script creates a deterministic cross-flag failure, runs Agent 2, records an
`interaction_findings` row, and resolves the associated escalations. An
`UNCLEAR` cause is expected because pair-level evidence confirms the harmful
combination but cannot identify a single responsible flag.

## Current scope

The prototype demonstrates the complete analysis logic with synthetic event
data. It intentionally keeps pair-level findings advisory: Agent 2 records the
evidence and recommends a controlled experiment instead of automatically
rolling back one flag without causal evidence.

## Future enhancements

- Publish relay decisions and application outcomes into `routing_events`.
- Run the agents automatically through a worker or scheduler.
- Add retry and exponential backoff for temporary Gemini failures.
- Add Alembic migrations instead of creating tables directly.
- Add Manager endpoints and a dashboard for escalations and findings.
- Add idempotency, authentication, observability, and production deployment
  configuration.
