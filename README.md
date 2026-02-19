# Harmony Take-Home (PO Workflow)

Minimal workflow engine for purchase-order ingestion:
- Parse PO email text into structured JSON
- Upsert PO + line items into Postgres
- Execute purchase-order tasks in DAG order
- Persist workflow/task state transitions
- Stop on first failed purchase order
- Write per-file alert JSON for each processed test file

## Project Layout

- `src/parse_txt.py`: deterministic `.txt` -> JSON parser
- `src/run_workflow.py`: workflow entrypoint
- `src/workflow/models.py`: purchase-order model/state
- `src/workflow/connectors.py`: abstract connector interfaces + txt/postgres connector implementations
- `src/workflow/dag.py`: discovery, dependencies, topological execution order
- `src/workflow/alerts.py`: deterministic attention rules + alert writer
- `db/docker-compose.yml`: Postgres + `dbcli` runner
- `db/init/001_schema.sql`: purchase order schema + upsert function
- `db/init/002_workflow.sql`: workflow run/task state tables + transition funcs
- `db/queries/*.sql`: helper SQL for load/query/visibility

## Prereqs

- Python 3.11+
- Docker Desktop / Docker Engine + Compose
- Python DB driver: `psycopg` or `psycopg2`

Example:
```powershell
pip install psycopg[binary]
```

## Quick Start

1. Start Postgres:
```powershell
cd db
docker compose up -d
```

2. Run workflow:
```powershell
cd ..
python src\run_workflow.py
```

Run a single suite folder:
```powershell
python src\run_workflow.py attention_suite
```

3. Inspect workflow/task state:
```powershell
cd db
docker compose run --rm dbcli /work/db/queries/04_workflow_visibility.sql
```

4. Stop Postgres:
```powershell
docker compose down
```

## Parser Only

Parse one test email to JSON (written next to input file):
```powershell
python src\parse_txt.py tests\attention_suite\input\no_flags.txt
```

## Data + Alert Outputs

- Parsed JSON: `tests/<suite_name>/parsed/<file>.json`
- Alert file: `tests/<suite_name>/alerts/<file>.alerts.json`

`<file>.alerts.json` includes:
- `po_number`
- `status` (`SUCCESS` or `FAILED`)
- `reasons` (deterministic triggers or failure reason)
- `fields` (parsed payload)
- `timestamp`

## Test Suite Convention

- Use `tests/<suite_name>/` for each suite.
- Put one or more PO docs at `tests/<suite_name>/input/*.txt`.
- Parsed outputs go to `tests/<suite_name>/parsed/`.
- Alert outputs go to `tests/<suite_name>/alerts/`.
- Optional DAG config at `tests/<suite_name>/dependencies.json`.
- `dependencies.json` format uses file stems:
  - `{ "file_b": ["file_a"] }` means `file_b.txt` runs after `file_a.txt`.

Example suites included:
- `tests/attention_suite/`: attention-flag scenarios
- `tests/order_success_then_fail/`: good PO runs first, then failing PO
- `tests/order_fail_first/`: same files but failing PO runs first (workflow stops before good PO)

