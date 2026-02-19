# Harmony Take-Home (PO Workflow)

Minimal workflow engine for purchase-order ingestion:
- Parse PO email text into structured JSON
- Upsert PO + line items into Postgres
- Execute purchase-order tasks in DAG order
- Persist workflow/task state transitions
- Stop on first failed purchase order
- Write `alerts.json` for each processed test folder

## Project Layout

- `src/parse_txt.py`: deterministic `.txt` -> JSON parser
- `src/run_workflow.py`: workflow entrypoint
- `src/workflow/models.py`: purchase-order model/state
- `src/workflow/connectors.py`: email and database connectors
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
python src\parse_txt.py tests\test1\test1.txt
```

## Data + Alert Outputs

- Parsed JSON: `tests/test<n>/test<n>.json`
- Alert file: `tests/test<n>/alerts.json`

`alerts.json` includes:
- `po_number`
- `status` (`SUCCESS` or `FAILED`)
- `reasons` (deterministic triggers or failure reason)
- `fields` (parsed payload)
- `timestamp`

