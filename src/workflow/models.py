from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

VALID_STATES = {"PENDING", "RUNNING", "SUCCESS", "FAILED"}


@dataclass
class PurchaseOrder:
    name: str
    txt_path: Path
    attention_priority_hint: int = 2
    order_date_hint: date | None = None
    req: dict[str, Any] | None = None
    state: str = "PENDING"
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise ValueError(f"invalid state: {self.state}")

    @property
    def test_dir(self) -> Path:
        if self.txt_path.parent.name == "input":
            return self.txt_path.parent.parent
        return self.txt_path.parent

    @property
    def json_path(self) -> Path:
        return self.test_dir / "parsed" / f"{self.txt_path.stem}.json"

    @property
    def alert_path(self) -> Path:
        return self.test_dir / "alerts" / f"{self.txt_path.stem}.alerts.json"

    @property
    def response_path(self) -> Path:
        return self.test_dir / "response" / f"{self.txt_path.stem}.response.txt"
