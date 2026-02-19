import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader  # type: ignore
except ImportError:
    PdfReader = None


LABEL_PATTERN = re.compile(r"^(?P<label>[A-Za-z][A-Za-z ]+):\s*(?P<value>.*)$")
LINE_ITEM_PATTERN = re.compile(
    r"^(?P<item_no>\d+)\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<qty>[\d,]+)\s+"
    r"\$?(?P<unit_price>[\d,]+\.\d{2})\s+"
    r"\$?(?P<total>[\d,]+\.\d{2})$"
)
TOTAL_PATTERN = re.compile(
    r"^(?P<label>Subtotal|Shipping|TOTAL|Tax(?:\s*\((?P<tax_rate>[^)]+)\))?):\s*"
    r"\$?(?P<amount>[\d,]+\.\d{2})$",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}|\(\d{3}\)\s*\d{3}-\d{4}")
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def to_float(value: str) -> float:
    return float(value.replace(",", "").strip())


def to_int(value: str) -> int:
    return int(value.replace(",", "").strip())


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


def find_line(lines: list[str], target: str) -> int:
    for idx, line in enumerate(lines):
        if line.strip().lower() == target.lower():
            return idx
    return -1


def parse_email_headers(lines: list[str]) -> tuple[dict[str, str], int]:
    headers: dict[str, str] = {}
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            break
        match = LABEL_PATTERN.match(line)
        if match:
            key = normalize_key(match.group("label"))
            headers[key] = match.group("value").strip()
        idx += 1
    return headers, idx


def parse_po_fields(lines: list[str]) -> dict[str, Any]:
    po: dict[str, Any] = {
        "po_number": None,
        "vendor": None,
        "ship_to": {"name": None, "address_lines": [], "full": None},
        "order_date": None,
        "due_date": None,
        "payment_terms": None,
    }
    idx = 0
    while idx < len(lines):
        raw = lines[idx].strip()
        if not raw:
            idx += 1
            continue
        if raw.startswith("PO Number:"):
            po["po_number"] = raw.split(":", 1)[1].strip()
        elif raw.startswith("Vendor:"):
            po["vendor"] = raw.split(":", 1)[1].strip()
        elif raw.startswith("Ship To:"):
            name = raw.split(":", 1)[1].strip()
            address_lines: list[str] = []
            look_ahead = idx + 1
            while look_ahead < len(lines):
                candidate = lines[look_ahead].strip()
                if not candidate:
                    look_ahead += 1
                    continue
                if candidate.startswith(("Order Date:", "Due Date:", "Payment Terms:")):
                    break
                if LABEL_PATTERN.match(candidate):
                    break
                address_lines.append(candidate)
                look_ahead += 1
            po["ship_to"] = {
                "name": name or None,
                "address_lines": address_lines,
                "full": ", ".join([part for part in [name, *address_lines] if part]),
            }
            idx = look_ahead - 1
        elif raw.startswith("Order Date:"):
            po["order_date"] = raw.split(":", 1)[1].strip()
        elif raw.startswith("Due Date:"):
            po["due_date"] = raw.split(":", 1)[1].strip()
        elif raw.startswith("Payment Terms:"):
            po["payment_terms"] = raw.split(":", 1)[1].strip()
        idx += 1
    return po


def parse_line_items(lines: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in lines:
        candidate = line.strip()
        if not candidate or candidate.lower().startswith("item description"):
            continue
        match = LINE_ITEM_PATTERN.match(candidate)
        if not match:
            continue
        items.append(
            {
                "item_no": int(match.group("item_no")),
                "description": match.group("description").strip(),
                "qty": to_int(match.group("qty")),
                "unit_price": to_float(match.group("unit_price")),
                "total": to_float(match.group("total")),
            }
        )
    return items


def parse_totals(lines: list[str]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "subtotal": None,
        "tax": {"rate": None, "amount": None},
        "shipping": None,
        "total": None,
    }
    for line in lines:
        candidate = line.strip()
        if not candidate:
            continue
        match = TOTAL_PATTERN.match(candidate)
        if not match:
            continue
        label = match.group("label").lower()
        amount = to_float(match.group("amount"))
        if label.startswith("subtotal"):
            totals["subtotal"] = amount
        elif label.startswith("shipping"):
            totals["shipping"] = amount
        elif label.startswith("total"):
            totals["total"] = amount
        elif label.startswith("tax"):
            totals["tax"]["amount"] = amount
            totals["tax"]["rate"] = match.group("tax_rate")
    return totals


def parse_notes_and_signoff(lines: list[str]) -> tuple[list[str], dict[str, Any]]:
    notes: list[str] = []
    signoff: dict[str, Any] = {
        "name": None,
        "title": None,
        "company": None,
        "phone": None,
        "email": None,
        "raw_lines": [],
    }

    thank_you_index = -1
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("thank you"):
            thank_you_index = idx
            break

    if thank_you_index == -1:
        notes = [line.strip() for line in lines if line.strip()]
        return notes, signoff

    notes = [line.strip() for line in lines[:thank_you_index] if line.strip()]
    closing = [line.strip() for line in lines[thank_you_index + 1 :] if line.strip()]
    signoff["raw_lines"] = closing

    if closing:
        signoff["name"] = closing[0]
    if len(closing) > 1:
        signoff["title"] = closing[1]
    if len(closing) > 2:
        signoff["company"] = closing[2]

    for line in closing:
        if signoff["phone"] is None:
            phone_match = PHONE_PATTERN.search(line)
            if phone_match:
                signoff["phone"] = phone_match.group(0)
        if signoff["email"] is None:
            email_match = EMAIL_PATTERN.search(line)
            if email_match:
                signoff["email"] = email_match.group(0)

    return notes, signoff


def parse_purchase_order_text(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    headers, body_start = parse_email_headers(lines)

    po_start = find_line(lines, "PURCHASE ORDER")
    line_items_start = find_line(lines, "LINE ITEMS")
    notes_start = find_line(lines, "Notes:")

    po_fields_lines = (
        lines[po_start + 1 : line_items_start]
        if po_start != -1 and line_items_start != -1 and po_start < line_items_start
        else []
    )
    line_items_lines = (
        lines[line_items_start + 1 : notes_start]
        if line_items_start != -1 and notes_start != -1 and line_items_start < notes_start
        else []
    )
    notes_lines = lines[notes_start + 1 :] if notes_start != -1 else []

    po_fields = parse_po_fields(po_fields_lines)
    line_items = parse_line_items(line_items_lines)
    totals = parse_totals(line_items_lines)
    notes, signoff = parse_notes_and_signoff(notes_lines)

    return {
        "email": headers,
        "message_intro": [
            line.strip()
            for line in lines[body_start + 1 : po_start]
            if line.strip()
        ]
        if po_start != -1
        else [],
        "purchase_order": {
            **po_fields,
            "line_items": line_items,
            "totals": totals,
            "notes": notes,
            "contact": signoff,
        },
    }


def extract_text_from_pdf(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("PDF input requires pypdf. Install with: pip install pypdf")

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def load_input_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    return path.read_text(encoding="utf-8", errors="replace")


def default_input_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    preferred = [root / "text1.txt", root / "tests" / "test1" / "test1.txt"]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    return preferred[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse purchase-order text into JSON.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(default_input_path()),
        help="Path to the purchase-order input file (.txt or .pdf).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output JSON path. Defaults to <input_dir>/<input_stem>.json",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    text = load_input_text(input_path)
    parsed = parse_purchase_order_text(text)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.parent / f"{input_path.stem}.json"
    )
    output_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
