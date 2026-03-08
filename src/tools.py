from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis
from .config import REDIS_URL, STREAM_KEY


class StellToolAwareness:
    def __init__(self) -> None:
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.stream_key = STREAM_KEY

    def _emit_tool_request(self, tool_name: str, action: str, params: dict[str, Any]) -> str:
        event_id = f"tool-req-{uuid.uuid4()}"
        envelope = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "stell-ai.tools",
            "type": f"tool.{tool_name}.{action}",
            "payload": params,
        }
        self.redis.xadd(self.stream_key, {"payload": json.dumps(envelope, ensure_ascii=True)})
        return event_id

    def request_3d_metadata(self, file_path: str) -> str:
        """Requests metadata from viewer3d (e.g., bounding box, volume)."""
        return self._emit_tool_request("viewer3d", "get_metadata", {"file_path": file_path})

    def request_2d_metadata(self, file_path: str) -> str:
        """Requests metadata from docviewer/viewer2d (e.g., drawing info, title block)."""
        return self._emit_tool_request("viewer2d", "get_metadata", {"file_path": file_path})

    def trigger_conversion(self, source_path: str, target_format: str) -> str:
        """Triggers a file conversion via the convert pipeline."""
        return self._emit_tool_request("converter", "start", {
            "source_path": source_path,
            "target_format": target_format
        })

    def analyze_drawing(self, file_path: str) -> str:
        """Requests a deep analysis of a technical drawing via docviewer."""
        return self._emit_tool_request("docviewer", "analyze", {"file_path": file_path})
