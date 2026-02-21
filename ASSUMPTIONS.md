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
- Execution order: DAG constraints, then `urgent`, then `due_soon`, then PO `Order Date`, then alphabetical fallback.
- Attention flags are deterministic: `urgent`, `due_soon`, `missing_fields`, `amount_exceeds_threshold`.
- `due_soon` is evaluated against `order_date` + N days (not wall-clock date), so the same input produces the same result.
- `amount_exceeds_threshold` uses `ATTENTION_TOTAL_THRESHOLD` (default `15000`).
- Failure policy is separate: fail on `out_of_stock` or `missing_fields`.
- If a task fails, independent downstream tasks still run.
- Only tasks that depend on failed tasks stay `PENDING` (`waiting_on_upstream` / `waiting_on_dependency`).


## Database

- Schema inferred from `desc.txt` sample requirements.
- Includes PO upsert, line items, alerts, workflow/task states, transition history, and stock tables.
- Postgres is source of truth for state.
- State model: `PENDING -> RUNNING -> SUCCESS|FAILED`.
- State survives process restarts (not memory-only).
- All discovered tasks are created in `purchase_order_runs` immediately, so blocked tasks are persisted as `PENDING` too.
- Visibility is query-based: running vs historical runs in `db/queries/04_workflow_visibility.sql`.
- Manual stock policy: fixed product stock in DB; each PO reserves stock; insufficient stock => `out_of_stock`.
- Stock reservation is skipped when parsed `po_number` is missing to avoid invalid shared reservations.

## Runtime

- Python 3.11+ runtime.
- Docker Compose for Postgres.
- DB driver: `psycopg` (or `psycopg2` fallback).
- PDF parser: `pypdf`.
- Optional demo visibility helper: `--simulate-latency`.
