# Harmony Take-Home (PO Workflow)
## [View the Workflow Diagram](https://lucid.app/lucidchart/7a32a848-fb27-4a4f-b108-750f03f2a093/edit?viewport_loc=-2738%2C-1471%2C4955%2C2792%2C0_0&invitationId=inv_7e049bbd-d488-401d-a996-f9e93608f79d)
Minimal workflow engine for purchase-order ingestion:
- Parse PO email text into structured JSON
- Upsert PO + line items into Postgres
- Execute purchase-order tasks in DAG order
- Persist workflow/task state transitions
- Continue independent tasks when an unrelated task fails
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
|   |   |-- 002_workflow.sql          # workflow/task states + transitions
|   |   `-- 003_stock.sql             # inventory + stock reservation tables
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
pip install psycopg[binary] pypdf
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
docker compose run --rm dbcli -f /work/db/queries/04_workflow_visibility.sql
```

This shows:
- previous workflow runs
- currently running workflows (`state = RUNNING`)
- currently running tasks (`purchase_order_runs.state = RUNNING`)
- per-run task counts (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`)
- recent task transitions

State is persisted in Postgres, so run history survives process restarts. Each discovered task is inserted into `purchase_order_runs` at workflow start, even if it later stays blocked in `PENDING`.

Inspect stock levels/consumption:
```powershell
docker compose run --rm dbcli -f /work/db/queries/05_stock_visibility.sql
```

Console output includes:
- Task start/end
- State transitions (`PENDING -> RUNNING -> SUCCESS|FAILED`)
- Failure messages
- Final workflow status (`COMPLETED` or `FAILED`)

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
- Response summary: `tests/<suite_name>/response/summary.txt`

`<file>.alerts.json` includes:
- `po_number`
- `status` (`SUCCESS` or `FAILED`)
- `reasons` (deterministic triggers or failure reason)
- `fields` (parsed payload)
- `timestamp`

## Test Suite Convention

- Use `tests/<suite_name>/` for each suite.
- Put one or more PO docs at `tests/<suite_name>/input/*.(txt|pdf)`.
- Parsed outputs go to `tests/<suite_name>/parsed/`.
- Alert outputs go to `tests/<suite_name>/alerts/`.
- Suite follow-up summary goes to `tests/<suite_name>/response/summary.txt`.
- Optional DAG config at `tests/<suite_name>/dependencies.json`.
- `dependencies.json` format uses file stems:
  - `{ "file_b": ["file_a"] }` means `file_b.txt` runs after `file_a.txt`.

Example suites included:
- `tests/attention_suite/`: attention-flag scenarios
- `tests/order_success_then_fail/`: good PO runs first, then failing PO
- `tests/order_fail_first/`: same files but failing PO runs first (dependent tasks stay pending)
- `tests/scenario_priority_ordering/`: no dependencies; shows priority + PO-date + alpha ordering
- `tests/scenario_dependency_branching/`: failed branch + independent branch continues
- `tests/scenario_dependency_waiting/`: demonstrates `waiting_on_upstream` vs `waiting_on_dependency`

## Stock Model

- Stock is manually configured in `db/init/003_stock.sql`.
- Fixed SKU list: `label_roll`, `sleeve_pack`, `neck_band`, `generic_label`.
- Each PO consumes stock based on line-item description mapping.
- If stock is insufficient, task is flagged `out_of_stock` and fails (`FAILED`).

