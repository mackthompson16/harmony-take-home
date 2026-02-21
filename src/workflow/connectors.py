import json
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any

from parse_txt import load_input_text, parse_purchase_order_text
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
    def set_purchase_order_request(
        self,
        purchase_order_run_id: int,
        req_payload: dict[str, Any],
        po_number: str | None = None,
    ) -> None:
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

    @abstractmethod
    def reserve_stock(self, po_number: str, line_items: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        raise NotImplementedError


class TxtEmailConnector(EmailConnectorBase):
    def __init__(self, default_path: Path | None = None) -> None:
        self.default_path = default_path

    def _resolve_path(self, path: Path | None) -> Path:
        if path is not None:
            return path
        if self.default_path is not None:
            return self.default_path
        return Path.cwd() / "tests" / "attention_suite" / "input" / "no_flags.txt"

    def read_text(self, path: Path | None = None) -> str:
        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Email input file not found: {resolved}")
        return load_input_text(resolved)

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

    def _ensure_stock_schema(self) -> None:
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS inventory_items (
                sku TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                available_qty INTEGER NOT NULL CHECK (available_qty >= 0),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS purchase_order_stock_usage (
                po_number TEXT NOT NULL,
                sku TEXT NOT NULL REFERENCES inventory_items(sku) ON DELETE CASCADE,
                reserved_qty INTEGER NOT NULL CHECK (reserved_qty >= 0),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (po_number, sku)
            );
            """,
            """
            INSERT INTO inventory_items (sku, description, available_qty) VALUES
                ('label_roll', 'General label rolls', 5000),
                ('sleeve_pack', 'Shrink sleeve packs', 3000),
                ('neck_band', 'Tamper neck bands', 4000),
                ('generic_label', 'Fallback label stock', 2000)
            ON CONFLICT (sku) DO NOTHING;
            """,
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for sql in sql_statements:
                    cur.execute(sql)
            conn.commit()

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

    def set_purchase_order_request(
        self,
        purchase_order_run_id: int,
        req_payload: dict[str, Any],
        po_number: str | None = None,
    ) -> None:
        sql = """
            UPDATE purchase_order_runs
            SET
                po_number = COALESCE(%s, po_number),
                req = %s::jsonb,
                updated_at = NOW()
            WHERE id = %s;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (po_number, json.dumps(req_payload), purchase_order_run_id))
            conn.commit()

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

    @staticmethod
    def _sku_from_description(description: str) -> str:
        normalized = description.lower()
        if "shrink sleeve" in normalized or "sleeve" in normalized:
            return "sleeve_pack"
        if "neck band" in normalized or "bands" in normalized:
            return "neck_band"
        if "label" in normalized:
            return "label_roll"
        return "generic_label"

    def reserve_stock(self, po_number: str, line_items: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        self._ensure_stock_schema()
        sku_qty: dict[str, int] = defaultdict(int)
        for item in line_items:
            qty = int(item.get("qty", 0))
            if qty <= 0:
                continue
            sku = self._sku_from_description(str(item.get("description", "")))
            sku_qty[sku] += qty

        if not sku_qty:
            return True, []

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    plan: list[tuple[str, int, int]] = []
                    insufficient: list[str] = []
                    for sku, requested_qty in sku_qty.items():
                        cur.execute("SELECT available_qty FROM inventory_items WHERE sku = %s FOR UPDATE;", (sku,))
                        stock_row = cur.fetchone()
                        if stock_row is None:
                            insufficient.append(f"{sku}(unknown)")
                            continue
                        available_qty = int(stock_row[0])

                        cur.execute(
                            "SELECT reserved_qty FROM purchase_order_stock_usage WHERE po_number = %s AND sku = %s FOR UPDATE;",
                            (po_number, sku),
                        )
                        reserved_row = cur.fetchone()
                        existing_reserved = int(reserved_row[0]) if reserved_row else 0
                        delta = requested_qty - existing_reserved
                        if delta > available_qty:
                            insufficient.append(f"{sku}(need_delta={delta},available={available_qty})")
                            continue
                        plan.append((sku, requested_qty, delta))

                    if insufficient:
                        conn.rollback()
                        return False, insufficient

                    for sku, requested_qty, delta in plan:
                        if delta != 0:
                            cur.execute(
                                "UPDATE inventory_items SET available_qty = available_qty - %s, updated_at = NOW() WHERE sku = %s;",
                                (delta, sku),
                            )
                        cur.execute(
                            """
                            INSERT INTO purchase_order_stock_usage (po_number, sku, reserved_qty, updated_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (po_number, sku)
                            DO UPDATE SET reserved_qty = EXCLUDED.reserved_qty, updated_at = NOW();
                            """,
                            (po_number, sku, requested_qty),
                        )

                conn.commit()
            return True, []
        except Exception as exc:  # noqa: BLE001
            return False, [f"stock_error:{exc}"]


# Backward-compatible names used by the workflow runner.
EmailConnector = TxtEmailConnector
DatabaseConnector = PostgresDatabaseConnector
