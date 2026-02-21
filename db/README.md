# Postgres Setup (Docker)
## 1) Schema

- Database: `harmony`
- User: `harmony`
- Password: `harmony`
- Host port: `5433`
- `dbcli` helper service preconfigured for `psql`

Schema is auto-initialized from:
- `db/init/001_schema.sql` (purchase orders + upsert)
- `db/init/002_workflow.sql` (workflow runs + persistent state transitions)

## 2) Workflow orchestration

From project root:
- Reads `tests/<suite>/input/*.(txt|pdf)` or `--input-file <path>`
- Extracts PO JSON and writes `tests/<suite>/parsed/<file>.json` (or `parsed/<file>.json` for single-file mode)
- Upserts PO rows in Postgres
- Applies deterministic attention checks
- Writes `tests/<suite>/alerts/<file>.alerts.json` (and writes `po_alert.json` in single-file mode when flagged)
- Persists transitions: `PENDING -> RUNNING -> SUCCESS|FAILED`
- Continues independent tasks after failures; dependent tasks remain `PENDING`

## 3) Visibility queries

From `db/`:

```powershell
docker compose run --rm dbcli /work/db/queries/04_workflow_visibility.sql
```

This shows:
- previous workflow runs
- currently running workflows
- currently running tasks
- per-workflow task state counts
- state transition history

```powershell
docker compose run --rm dbcli /work/db/queries/05_stock_visibility.sql
```

This shows current inventory and PO stock reservations.
