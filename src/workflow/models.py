from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_STATES = {"PENDING", "RUNNING", "SUCCESS", "FAILED"}


@dataclass
class PurchaseOrder:
    name: str
    txt_path: Path
    req: dict[str, Any] | None = None
    state: str = "PENDING"
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise ValueError(f"invalid state: {self.state}")

    @property
    def test_dir(self) -> Path:
        return self.txt_path.parent

    @property
    def json_path(self) -> Path:
        return self.test_dir / f"{self.txt_path.stem}.json"

    @property
    def alert_path(self) -> Path:
        return self.test_dir / "alerts.json"
