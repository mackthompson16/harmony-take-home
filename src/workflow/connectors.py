import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from parse_txt import parse_purchase_order_text
from workflow.models import PurchaseOrder

try:
    import psycopg  # type: ignore

    DB_DRIVER = "psycopg"
except ImportError:
    psycopg = None
    try:
        import psycopg2  # type: ignore

        DB_DRIVER = "psycopg2"
    except ImportError:
        psycopg2 = None
        DB_DRIVER = None


class EmailConnectorBase(ABC):
    @abstractmethod
    def read_text(self, path: Path | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def extract_purchase_order(self, path: Path | None = None) -> dict[str, Any]:
        raise NotImplementedError


class DatabaseConnectorBase(ABC):
    @abstractmethod
    def create_workflow_run(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def transition_workflow(self, run_id: int, new_state: str, error_message: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_purchase_order_run(self, workflow_run_id: int, po: PurchaseOrder) -> int:
        raise NotImplementedError

    @abstractmethod
    def set_attempts(self, purchase_order_run_id: int, attempts: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def transition_purchase_order(
        self, purchase_order_run_id: int, new_state: str, error_message: str | None = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_output(self, purchase_order_run_id: int, output_payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_purchase_order(self, payload: dict[str, Any]) -> int:
        raise NotImplementedError

    @abstractmethod
    def insert_alert(self, purchase_order_id: int, po_number: str, reasons: list[str], fields: dict[str, Any]) -> None:
        raise NotImplementedError


class TxtEmailConnector(EmailConnectorBase):
    def __init__(self, default_path: Path | None = None) -> None:
        self.default_path = default_path

    def _resolve_path(self, path: Path | None) -> Path:
        if path is not None:
            return path
        if self.default_path is not None:
            return self.default_path
        return Path.cwd() / "tests" / "test1" / "test1.txt"

    def read_text(self, path: Path | None = None) -> str:
        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Email input file not found: {resolved}")
        path = resolved
        return path.read_text(encoding="utf-8", errors="replace")

    def extract_purchase_order(self, path: Path | None = None) -> dict[str, Any]:
        raw = self.read_text(path)
        return parse_purchase_order_text(raw)


class PostgresDatabaseConnector(DatabaseConnectorBase):
    def __init__(self, dsn: str) -> None:
        if DB_DRIVER is None:
            raise RuntimeError("Install psycopg or psycopg2 to run workflow.")
        self.dsn = dsn

    def _connect(self):
        if DB_DRIVER == "psycopg":
            return psycopg.connect(self.dsn)  # type: ignore[union-attr]
        return psycopg2.connect(self.dsn)  # type: ignore[union-attr]

    def create_workflow_run(self) -> int:
        sql = "INSERT INTO workflow_runs (state) VALUES ('PENDING') RETURNING id;"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
            conn.commit()
        return int(row[0])

    def transition_workflow(self, run_id: int, new_state: str, error_message: str | None = None) -> None:
        sql = "SELECT transition_workflow_run(%s, %s, %s);"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id, new_state, error_message))
            conn.commit()

    def create_purchase_order_run(self, workflow_run_id: int, po: PurchaseOrder) -> int:
        po_number = ((po.req or {}).get("purchase_order") or {}).get("po_number")
        sql = "SELECT create_purchase_order_run(%s, %s, %s, %s::jsonb);"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (workflow_run_id, po.name, po_number, json.dumps(po.req or {})))
                row = cur.fetchone()
            conn.commit()
        return int(row[0])

    def set_attempts(self, purchase_order_run_id: int, attempts: int) -> None:
        sql = "UPDATE purchase_order_runs SET attempts = %s, updated_at = NOW() WHERE id = %s;"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (attempts, purchase_order_run_id))
            conn.commit()

    def transition_purchase_order(
        self, purchase_order_run_id: int, new_state: str, error_message: str | None = None
    ) -> None:
        sql = "SELECT transition_purchase_order_run(%s, %s, %s);"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (purchase_order_run_id, new_state, error_message))
            conn.commit()

    def set_output(self, purchase_order_run_id: int, output_payload: dict[str, Any]) -> None:
        sql = "UPDATE purchase_order_runs SET output = %s::jsonb, updated_at = NOW() WHERE id = %s;"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (json.dumps(output_payload), purchase_order_run_id))
            conn.commit()

    def upsert_purchase_order(self, payload: dict[str, Any]) -> int:
        sql = "SELECT upsert_purchase_order(%s::jsonb);"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (json.dumps(payload),))
                row = cur.fetchone()
            conn.commit()
        return int(row[0])

    def insert_alert(self, purchase_order_id: int, po_number: str, reasons: list[str], fields: dict[str, Any]) -> None:
        sql = """
            INSERT INTO po_alerts (purchase_order_id, po_number, reasons, fields)
            VALUES (%s, %s, %s, %s::jsonb);
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (purchase_order_id, po_number, reasons, json.dumps(fields)))
            conn.commit()


# Backward-compatible names used by the workflow runner.
EmailConnector = TxtEmailConnector
DatabaseConnector = PostgresDatabaseConnector
