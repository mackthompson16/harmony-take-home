# Harmony Take-Home (PO Workflow)

Minimal workflow engine for purchase-order ingestion:
- Parse PO email text into structured JSON
- Upsert PO + line items into Postgres
- Execute purchase-order tasks in DAG order
- Persist workflow/task state transitions
- Stop on first failed purchase order
- Write per-file alert JSON for each processed test file

## Project Layout

```text
harmony-take-home/
|-- src/
|   |-- parse_txt.py                  # txt -> structured JSON
|   |-- run_workflow.py               # workflow entrypoint (optionally per suite)
|   `-- workflow/
|       |-- connectors.py             # connector ABCs + txt/postgres implementations
|       |-- dag.py                    # discovery + dependency graph + topological sort
|       |-- alerts.py                 # deterministic attention rules + alert writer
|       `-- models.py                 # PurchaseOrder model + state
|-- db/
|   |-- docker-compose.yml            # postgres + dbcli
|   |-- init/
|   |   |-- 001_schema.sql            # PO schema + upsert function
|   |   `-- 002_workflow.sql          # workflow/task states + transitions
|   `-- queries/
|       |-- 01_load_test1_json.sql
|       |-- 02_get_purchase_order.sql
|       |-- 03_needs_attention.sql
|       `-- 04_workflow_visibility.sql
`-- tests/
    |-- <suite_name>/
    |   |-- input/                    # source PO txt files
    |   |-- parsed/                   # generated parsed JSON
    |   |-- alerts/                   # generated alert payloads
    |   `-- dependencies.json         # optional DAG config
    |-- attention_suite/
    |-- order_success_then_fail/
    `-- order_fail_first/
```

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

