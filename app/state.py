from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    kis_enabled: bool = False
    kis_position: dict[str, str | None] = field(default_factory=dict)
    kis_split: int = 1
    kis_buy_count: int = 0
    last_signal: dict[str, Any] | None = None

    def is_long(self, ticker: str) -> bool:
        return self.kis_position.get(ticker) == "long"
