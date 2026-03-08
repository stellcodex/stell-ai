from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import RUNS_DIR


class Reporter:
    def __init__(self) -> None:
        self.report_path = RUNS_DIR / "stell_ai_activation_events.jsonl"

    def write(self, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with self.report_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
