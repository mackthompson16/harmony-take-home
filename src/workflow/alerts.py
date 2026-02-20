import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from workflow.models import PurchaseOrder


def needs_attention(payload: dict[str, Any], due_within_days: int = 7) -> list[str]:
    reasons: list[str] = []
    po = payload.get("purchase_order", {})
    email = payload.get("email", {})
    totals = po.get("totals", {})

    due_date = po.get("due_date")
    if due_date:
        due = datetime.strptime(due_date, "%Y-%m-%d").date()
        if due <= (datetime.now(UTC).date() + timedelta(days=due_within_days)):
            reasons.append("due_soon")

    subject = (email.get("subject") or "").lower()
    if "urgent" in subject:
        reasons.append("urgent")

    required = [
        po.get("po_number"),
        po.get("vendor"),
        po.get("order_date"),
        po.get("due_date"),
        totals.get("total"),
    ]
    if any(value in (None, "") for value in required):
        reasons.append("missing_fields")

    return reasons


def failure_flags(reasons: list[str]) -> list[str]:
    fail_set = {"missing_fields", "out_of_stock"}
    return [reason for reason in reasons if reason in fail_set]


def priority_rank(reasons: list[str]) -> int:
    # Lower is higher queue priority (separate from failure policy).
    rank_map = {
        "urgent": 0,
        "due_soon": 1,
    }
    if not reasons:
        return 2
    # Only urgent/due_soon influence priority. Everything else is fallback tier.
    return min(rank_map.get(reason, 2) for reason in reasons)


def write_alert(po: PurchaseOrder, status: str, reasons: list[str], error_message: str | None = None) -> None:
    po_number = ((po.req or {}).get("purchase_order") or {}).get("po_number")
    payload = {
        "po_number": po_number,
        "status": status,
        "reasons": reasons,
        "fields": po.req or {},
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if error_message:
        payload["error"] = error_message
    po.alert_path.parent.mkdir(parents=True, exist_ok=True)
    po.alert_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_suite_response_summary(
    suite_dir: Path,
    suite_name: str,
    ordered_events: list[dict[str, Any]],
) -> None:
    response_dir = suite_dir / "response"
    response_dir.mkdir(parents=True, exist_ok=True)

    # Remove legacy per-task response files.
    for old in response_dir.glob("*.response.txt"):
        old.unlink(missing_ok=True)

    suite_status = "SUCCESS"
    if any(event["status"] in {"FAILED", "PENDING"} for event in ordered_events):
        suite_status = "FAILED"

    lines = [
        f"Suite: {suite_name}",
        f"Status: {suite_status}",
        "Execution:",
    ]

    for idx, event in enumerate(ordered_events, start=1):
        reason_text = ", ".join(event.get("reasons", [])) or "none"
        po_number = event.get("po_number") or "N/A"
        line = f"{idx}. {event['task']} | {event['status']} | flags={reason_text} | po={po_number}"
        if event.get("error"):
            short_error = re.sub(r"\s+", " ", str(event["error"])).strip()
            if len(short_error) > 120:
                short_error = short_error[:117] + "..."
            line += f" | error={short_error}"
        lines.append(line)

    (response_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
