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
- Reads `tests/test*/test*.txt`
- Extracts PO JSON and writes `test*.json`
- Upserts PO rows in Postgres
- Applies deterministic attention checks
- Writes `alerts.json` in each processed `tests/test<n>/`
- Persists transitions: `PENDING -> RUNNING -> SUCCESS|FAILED`
- Stops on first failed purchase order
