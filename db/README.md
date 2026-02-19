# Postgres Setup (Docker)

Run these from the `db/` directory.

## 1) Start Postgres

```powershell
.\up.ps1
```

This starts:
- Database: `harmony`
- User: `harmony`
- Password: `harmony`
- Host port: `5433`
- `dbcli` helper service preconfigured for `psql`

Schema is auto-initialized from:
- `db/init/001_schema.sql` (purchase orders + upsert)
- `db/init/002_workflow.sql` (workflow runs + persistent state transitions)

## 2) Run workflow orchestration

From project root:

```powershell
python src\run_workflow.py
```

What it does:
- Reads `tests/test*/test*.txt`
- Extracts PO JSON and writes `test*.json`
- Upserts PO rows in Postgres
- Applies deterministic attention checks
- Writes `alerts.json` in each processed `tests/test<n>/`
- Persists transitions: `PENDING -> RUNNING -> SUCCESS|FAILED`
- Stops on first failed purchase order

## 3) DB helper queries

Load prebuilt JSON test:

```powershell
.\load.ps1
```

Query PO + line items:

```powershell
.\query.ps1
```

Run needs-attention SQL:

```powershell
.\attention.ps1
```

Show workflow visibility:

```powershell
.\visibility.ps1
```

## 4) Stop DB

```powershell
.\down.ps1
```
