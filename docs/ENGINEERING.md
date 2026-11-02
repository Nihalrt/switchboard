# Engineering walkthrough

Switchboard explores predictable feature routing and failure investigation with synthetic data.

## Request and decision flow

1. [FastAPI flag routes](../manager/app/routers/flags.py) persist a rollout percentage in PostgreSQL and update Redis through [the cache adapter](../manager/app/cache.py).
2. [The Go relay](../relay/cmd/relay/main.go) validates a POST request before reading Redis.
3. [BucketFor](../relay/internal/routing/hash.go) maps the flag/device pair to a bucket from 1 to 100. Increasing a flag's percentage includes more buckets without changing assignments.
4. Redis failures or invalid percentages route to legacy. Request handling is covered by [fake-store tests](../relay/cmd/relay/main_test.go).

## Analysis flow

[Agent 1](../agents/Agent1.py) compares completed success/failure outcomes for one flag. It requires enough samples and outcome variation before statistical analysis. It parses a constrained Gemini recommendation and rejects rollback when the new pipeline's observed failure rate is no worse than legacy.

[Agent 2](../agents/Agent2.py) consumes unresolved escalations, compares overlapping and comparison devices, and records an advisory finding. The [workflow tests](../agents/test_agent_2.py) exercise the handoff using SQLite and mocked Gemini output.

## Decisions and trade-offs

- Stable hashing makes rollout changes reproducible. Hash concatenation currently has no separator; changing that encoding would reassign devices and needs a migration plan.
- Redis keeps decision reads simple, but PostgreSQL writes and cache updates are not atomic. A cache failure can leave an old percentage in service until retried.
- A constrained LLM response still needs deterministic safeguards. Statistics filter inputs; the model does not establish causality.
- Pair findings are advisory. Any-failure aggregation, repeated historical observations, missing time windows, and multiple comparisons limit statistical interpretation.

## Reproduce the isolated tests

Run from the repository root after installing the agent dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r agents/requirements.txt
cd agents
GEMINI_API_KEY=test-key DATABASE_URL=sqlite:///:memory: \
../.venv/bin/python -m unittest discover -p 'test_agent_*.py' -v
cd ../relay
go test ./...
```

These checks exercise analysis persistence, recommendations, invalid relay input,
cache fallback, and bucket behavior. They do not verify live Redis/PostgreSQL,
real model calls, latency, or production traffic. The manual scenarios in the
[README](../README.md#tests) require separate services and a real Gemini key.

## Current boundary

Live event/outcome ingestion, authentication, rate limits, observation windows,
and transactional cache synchronization are future work. Large-device stability and rollout-expansion measurements need a separate
reproducible harness before they can be treated as benchmarks.
