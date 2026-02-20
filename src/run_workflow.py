import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from workflow.alerts import failure_flags, needs_attention, write_alert, write_suite_response_summary
from workflow.connectors import DatabaseConnector, EmailConnector
from workflow.dag import discover_purchase_orders, load_dependencies, topo_sort


def run_workflow(suite: str | None = None, max_retries: int = 2, simulate_latency_seconds: float = 0.0) -> int:
    tests_root = Path(__file__).resolve().parent.parent / "tests"
    if suite:
        suite_dir = tests_root / suite
        if not suite_dir.exists() or not suite_dir.is_dir():
            raise RuntimeError(f"Suite '{suite}' not found at {suite_dir}")
    tasks = discover_purchase_orders(tests_root, suite_name=suite)
    if not tasks:
        if suite:
            raise RuntimeError(f"No test purchase-order files found in tests/{suite}/*.txt")
        raise RuntimeError("No test purchase-order files found in tests/<suite_name>/*.txt")

    dependencies = load_dependencies(tests_root, list(tasks.keys()), suite_name=suite)
    for name, deps in dependencies.items():
        if name in tasks:
            tasks[name].dependencies = deps

    order = topo_sort(tasks)
    dsn = os.getenv("POSTGRES_DSN", "postgresql://harmony:harmony@localhost:5433/harmony")
    email = EmailConnector()
    db = DatabaseConnector(dsn)

    workflow_run_id = db.create_workflow_run()
    print(f"Workflow run {workflow_run_id} created. State: PENDING -> RUNNING")
    db.transition_workflow(workflow_run_id, "RUNNING")
    task_run_ids: dict[str, int] = {}
    for task_id in order:
        task_run_ids[task_id] = db.create_purchase_order_run(workflow_run_id, tasks[task_id])

    completed: dict[str, str] = {}
    execution_events: list[dict[str, object]] = []
    workflow_failed = False

    def record_event(
        task_id: str,
        status: str,
        reasons: list[str],
        po_number: str | None = None,
        error_message: str | None = None,
    ) -> None:
        suite_name, task_name = task_id.split("/", 1)
        execution_events.append(
            {
                "suite": suite_name,
                "task": task_name,
                "status": status,
                "reasons": reasons,
                "po_number": po_number,
                "error": error_message,
            }
        )

    def write_all_suite_summaries() -> None:
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for event in execution_events:
            grouped[str(event["suite"])].append(event)
        for suite_name, events in grouped.items():
            suite_dir = tests_root / suite_name
            write_suite_response_summary(suite_dir, suite_name, events)

    latency_seconds = max(0.0, simulate_latency_seconds)

    for task_name in order:
        po = tasks[task_name]
        po_run_id = task_run_ids[task_name]
        print(f"TASK START: {task_name}")
        unmet = [dep for dep in po.dependencies if completed.get(dep) != "SUCCESS"]
        if unmet:
            message = f"Dependencies not satisfied for {task_name}: {', '.join(unmet)}"
            unmet_failed = any(completed.get(dep) == "FAILED" for dep in unmet)
            pending_flag = "waiting_on_upstream" if unmet_failed else "waiting_on_dependency"
            print(f"{task_name}: PENDING ({pending_flag})")
            db.set_output(
                po_run_id,
                {
                    "status": "PENDING",
                    "reasons": [pending_flag],
                    "error": message,
                },
            )
            write_alert(po, "PENDING", [pending_flag], message)
            po_number = ((po.req or {}).get("purchase_order") or {}).get("po_number")
            record_event(task_name, "PENDING", [pending_flag], po_number, message)
            completed[task_name] = "PENDING"
            print(f"TASK END: {task_name} -> PENDING")
            continue

        try:
            po.state = "RUNNING"
            print(f"{task_name}: PENDING -> RUNNING")
            db.transition_purchase_order(po_run_id, "RUNNING")
            if latency_seconds > 0:
                time.sleep(latency_seconds)
            success = False
            last_error_message: str | None = None
            last_reasons: list[str] = ["task_execution_failed"]

            for attempt in range(1, max_retries + 2):
                db.set_attempts(po_run_id, attempt)
                try:
                    po.req = email.extract_purchase_order(po.txt_path)
                    po.json_path.parent.mkdir(parents=True, exist_ok=True)
                    po.json_path.write_text(json.dumps(po.req, indent=2), encoding="utf-8")
                    parsed_po_number = (po.req.get("purchase_order") or {}).get("po_number")
                    db.set_purchase_order_request(po_run_id, po.req, parsed_po_number)

                    reasons = needs_attention(po.req)
                    po_number_for_stock = (po.req.get("purchase_order") or {}).get("po_number") or ""
                    line_items_for_stock = (po.req.get("purchase_order") or {}).get("line_items") or []
                    if po_number_for_stock:
                        stock_ok, stock_details = db.reserve_stock(po_number_for_stock, line_items_for_stock)
                        if not stock_ok:
                            reasons = reasons + ["out_of_stock"]
                            if stock_details:
                                reasons.append(f"stock_detail:{';'.join(stock_details)}")

                    fail_reasons = failure_flags(reasons)
                    if fail_reasons:
                        last_reasons = reasons
                        raise RuntimeError(",".join(fail_reasons))

                    po_id = db.upsert_purchase_order(po.req)
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
                    po_number = (po.req.get("purchase_order") or {}).get("po_number")
                    record_event(task_name, "SUCCESS", reasons, po_number)
                    print(f"{task_name}: RUNNING -> SUCCESS")
                    print(f"TASK END: {task_name} -> SUCCESS")
                    success = True
                    break
                except Exception as exc:  # noqa: BLE001
                    error_message = str(exc)
                    last_error_message = error_message
                    if error_message and last_reasons == ["task_execution_failed"]:
                        tokens = [token.strip() for token in error_message.split(",") if token.strip()]
                        if tokens:
                            if all(token in {"missing_fields", "out_of_stock"} for token in tokens):
                                last_reasons = tokens
                            elif "missing_fields" in tokens or "out_of_stock" in tokens:
                                last_reasons = [token for token in tokens if token in {"missing_fields", "out_of_stock"}]
                    if attempt <= max_retries:
                        print(f"{task_name}: retry {attempt}/{max_retries} after error: {error_message}")
                        continue

            if not success:
                final_error = last_error_message or "task_execution_failed"
                db.transition_purchase_order(po_run_id, "FAILED", final_error)
                po.state = "FAILED"
                completed[task_name] = "FAILED"
                workflow_failed = True
                write_alert(po, "FAILED", last_reasons, final_error)
                po_number = ((po.req or {}).get("purchase_order") or {}).get("po_number")
                record_event(task_name, "FAILED", last_reasons, po_number, final_error)
                print(f"{task_name}: RUNNING -> FAILED ({final_error})")
                print(f"TASK END: {task_name} -> FAILED")
                continue
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            po.state = "FAILED"
            completed[task_name] = "FAILED"
            workflow_failed = True
            db.transition_purchase_order(po_run_id, "FAILED", message)
            write_alert(po, "FAILED", ["task_setup_failed"], message)
            po_number = ((po.req or {}).get("purchase_order") or {}).get("po_number")
            record_event(task_name, "FAILED", ["task_setup_failed"], po_number, message)
            print(f"{task_name}: FAILED ({message})")
            print(f"TASK END: {task_name} -> FAILED")
            continue

    if workflow_failed:
        db.transition_workflow(workflow_run_id, "FAILED", "one_or_more_tasks_failed")
        final_status = "FAILED"
    else:
        db.transition_workflow(workflow_run_id, "SUCCESS")
        final_status = "COMPLETED"
    write_all_suite_summaries()
    print(f"Final workflow status: {final_status}")
    return 1 if workflow_failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run purchase-order workflow.")
    parser.add_argument(
        "suite",
        nargs="?",
        default=None,
        help="Optional suite folder under tests/ (example: attention_suite).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of retries after first attempt for each task.",
    )
    parser.add_argument(
        "--simulate-latency",
        type=float,
        default=0.0,
        help="Optional per-task sleep in seconds after entering RUNNING (demo visibility helper).",
    )
    args = parser.parse_args()
    try:
        raise SystemExit(
            run_workflow(
                suite=args.suite,
                max_retries=args.retries,
                simulate_latency_seconds=args.simulate_latency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        raise SystemExit(1)
