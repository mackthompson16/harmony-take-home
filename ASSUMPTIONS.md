# Assumptions

## Scope Boundaries

- This implementation is a local, single-process workflow runner (no distributed workers).
- It targets the core demo path: read PO input -> parse fields -> upsert DB -> evaluate attention -> emit alerts.
- Console visibility and persisted task/workflow state are included; advanced scheduling/orchestration features are out of scope.

## Input/Parsing Assumptions

- PO inputs are expected to follow a consistent structure/nomenclature (as in the provided sample).
- Parsing is deterministic and regex/string-rule based (no NLP, no fuzzy matching).
- Because of this, the parser is intentionally brittle: major format drift or missing labels can lead to partial extraction or failure.
- Inputs can be `.txt` or `.pdf`; PDFs are expected to contain extractable text in the same logical format as `.txt`.

## Dependency Ordering Assumptions

- The assignment language around dependency definition was ambiguous, so dependencies are provided explicitly via `tests/<suite>/dependencies.json` when needed.
- If no dependency file is provided, tasks are executed in deterministic alphabetical order by file name.
- We currently do **not** infer task dependencies from parsed PO JSON content.
  - That could be added later, but would require clear business rules (e.g., PO references, dates, vendor-level sequencing).
- A future improvement could support time-based ordering (e.g., by file modified time or PO order date) when dependencies are absent.

## Database Assumptions

- Schema design was inferred from the `desc.txt` requirements and sample flow:
  - purchase order storage/upsert
  - line items
  - alerts
  - workflow/task run state persistence + transition history
- Postgres is the source of truth for run/task states.
- State model is strict: `PENDING -> RUNNING -> SUCCESS | FAILED`.

## Runtime/Package Assumptions

- Python 3.11+ runtime.
- Postgres runs via Docker Compose.
- Python DB driver: `psycopg` (or `psycopg2` fallback).
- PDF parsing requires `pypdf`.
- Environment is expected to provide Docker and local file-system access to `tests/`.
