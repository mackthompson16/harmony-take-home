# Assumptions

## Scope

- Single-process, local runner (no distributed workers).
- Goal: input -> parse -> upsert -> attention check -> alert output.
- Includes console visibility + persisted run/task states.

## Parsing

- Assumes consistent PO format/nomenclature (sample-like).
- Deterministic regex parser (no NLP).
- Intentionally brittle to format drift.
- Supports `.txt` and text-extractable `.pdf`.

## DAG / Ordering

- Explicit dependencies: `tests/<suite>/dependencies.json` (optional).
- No dependency inference from parsed JSON.
- If dependencies are missing: sort by PO `Order Date` (from document), then alphabetical.

## Database

- Schema inferred from `desc.txt` sample requirements.
- Includes PO upsert, line items, alerts, workflow/task states, transition history.
- Postgres is source of truth for state.
- State model: `PENDING -> RUNNING -> SUCCESS|FAILED`.

## Runtime

- Python 3.11+ runtime.
- Docker Compose for Postgres.
- DB driver: `psycopg` (or `psycopg2` fallback).
- PDF parser: `pypdf`.
