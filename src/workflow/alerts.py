import json
from datetime import UTC, datetime, timedelta
from typing import Any

from workflow.models import PurchaseOrder


def needs_attention(payload: dict[str, Any], amount_threshold: float = 15000.0, due_within_days: int = 7) -> list[str]:
    reasons: list[str] = []
    po = payload.get("purchase_order", {})
    email = payload.get("email", {})
    totals = po.get("totals", {})

    total = totals.get("total")
    if isinstance(total, (int, float)) and total > amount_threshold:
        reasons.append("amount_exceeds_threshold")

    due_date = po.get("due_date")
    if due_date:
        due = datetime.strptime(due_date, "%Y-%m-%d").date()
        if due <= (datetime.now(UTC).date() + timedelta(days=due_within_days)):
            reasons.append("due_soon")

    subject = (email.get("subject") or "").lower()
    if "urgent" in subject:
        reasons.append("subject_contains_urgent")

    required = [
        po.get("po_number"),
        po.get("vendor"),
        po.get("order_date"),
        po.get("due_date"),
        totals.get("total"),
    ]
    if any(value in (None, "") for value in required):
        reasons.append("required_fields_missing")

    return reasons


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
