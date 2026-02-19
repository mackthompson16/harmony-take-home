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
- Execution order:
  1. dependency DAG constraints
  2. attention priority (deterministic flag metric)
    - metric:
    - `0`: `urgent`
    - `1`: `due_soon`
    - `2`: all others (`no_flags`, `exceeds_threshold`, `missing_fields`)
    - failure policy is separate: fail on `exceeds_threshold` or `missing_fields`
  3. PO `Order Date`
  4. alphabetical fallback
- If a task fails, independent downstream tasks still run.
- Only tasks that depend on failed tasks stay `PENDING` (`waiting_on_upstream` / `waiting_on_dependency`).


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
