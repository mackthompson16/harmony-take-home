import json
import os
from pathlib import Path

from workflow.alerts import needs_attention, write_alert
from workflow.connectors import DatabaseConnector, EmailConnector
from workflow.dag import discover_purchase_orders, load_dependencies, topo_sort


def run_workflow(max_retries: int = 2) -> int:
    tests_root = Path(__file__).resolve().parent.parent / "tests"
    tasks = discover_purchase_orders(tests_root)
    if not tasks:
        raise RuntimeError("No test purchase-order files found in tests/test*/test*.txt")

    dependencies = load_dependencies(tests_root, list(tasks.keys()))
    for name, deps in dependencies.items():
        if name in tasks:
            tasks[name].dependencies = deps

    order = topo_sort(tasks)
    dsn = os.getenv("POSTGRES_DSN", "postgresql://harmony:harmony@localhost:5433/harmony")
    db = DatabaseConnector(dsn)

    workflow_run_id = db.create_workflow_run()
    print(f"Workflow run {workflow_run_id} created. State: PENDING -> RUNNING")
    db.transition_workflow(workflow_run_id, "RUNNING")

    completed: dict[str, str] = {}

    for task_name in order:
        po = tasks[task_name]
        unmet = [dep for dep in po.dependencies if completed.get(dep) != "SUCCESS"]
        if unmet:
            message = f"Dependencies not satisfied for {task_name}: {', '.join(unmet)}"
            print(f"{task_name}: FAILED ({message})")
            write_alert(po, "FAILED", ["dependencies_not_satisfied"], message)
            db.transition_workflow(workflow_run_id, "FAILED", message)
            return 1

        try:
            po.req = EmailConnector.extract_purchase_order(po.txt_path)
            po.json_path.write_text(json.dumps(po.req, indent=2), encoding="utf-8")

            po_run_id = db.create_purchase_order_run(workflow_run_id, po)
            po.state = "RUNNING"
            print(f"{task_name}: PENDING -> RUNNING")
            db.transition_purchase_order(po_run_id, "RUNNING")

            for attempt in range(1, max_retries + 2):
                db.set_attempts(po_run_id, attempt)
                try:
                    po_id = db.upsert_purchase_order(po.req)
                    reasons = needs_attention(po.req)
                    po_number = (po.req.get("purchase_order") or {}).get("po_number") or task_name

                    if reasons:
                        db.insert_alert(po_id, po_number, reasons, po.req)

                    db.set_output(
                        po_run_id,
                        {"purchase_order_id": po_id, "reasons": reasons, "attempts": attempt},
                    )
                    db.transition_purchase_order(po_run_id, "SUCCESS")
                    po.state = "SUCCESS"
                    completed[task_name] = "SUCCESS"
                    write_alert(po, "SUCCESS", reasons)
                    print(f"{task_name}: RUNNING -> SUCCESS")
                    break
                except Exception as exc:  # noqa: BLE001
                    error_message = str(exc)
                    if attempt <= max_retries:
                        print(f"{task_name}: retry {attempt}/{max_retries} after error: {error_message}")
                        continue

                    db.transition_purchase_order(po_run_id, "FAILED", error_message)
                    po.state = "FAILED"
                    completed[task_name] = "FAILED"
                    write_alert(po, "FAILED", ["task_execution_failed"], error_message)
                    print(f"{task_name}: RUNNING -> FAILED ({error_message})")
                    db.transition_workflow(workflow_run_id, "FAILED", error_message)
                    return 1
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            po.state = "FAILED"
            completed[task_name] = "FAILED"
            write_alert(po, "FAILED", ["task_setup_failed"], message)
            print(f"{task_name}: FAILED ({message})")
            db.transition_workflow(workflow_run_id, "FAILED", message)
            return 1

    db.transition_workflow(workflow_run_id, "SUCCESS")
    print(f"Workflow run {workflow_run_id} completed: SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_workflow())
