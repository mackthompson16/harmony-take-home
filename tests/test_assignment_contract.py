import tempfile
import unittest
from pathlib import Path
import sys
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workflow.alerts import needs_attention, write_alert
from workflow.models import PurchaseOrder


class AssignmentContractTests(unittest.TestCase):
    def test_due_soon_uses_order_date_anchor(self) -> None:
        payload = {
            "email": {"subject": "Purchase Order"},
            "purchase_order": {
                "po_number": "PO-1",
                "vendor": "Vendor",
                "order_date": "2025-06-18",
                "due_date": "2025-06-25",
                "totals": {"total": 100.0},
            },
        }
        reasons = needs_attention(payload, due_within_days=7)
        self.assertIn("due_soon", reasons)

    def test_unflagged_success_can_skip_alert_file(self) -> None:
        root = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent))
        try:
            po = PurchaseOrder(name="demo/sample", txt_path=root / "sample.txt")
            po.req = {
                "purchase_order": {"po_number": "PO-2"},
            }
            output_path = root / "po_alert.json"
            wrote = write_alert(
                po,
                status="SUCCESS",
                reasons=[],
                output_path=output_path,
                write_for_unflagged_success=False,
            )
            self.assertFalse(wrote)
            self.assertFalse(output_path.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
