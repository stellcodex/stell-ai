from __future__ import annotations

import json
from typing import Any


class Planner:
    def plan(self, raw_fields: dict[str, str]) -> list[dict[str, Any]]:
        payload = raw_fields.get("payload")
        if not payload:
            return [{"action": "periodic_sync", "reason": "empty_payload"}]

        try:
            envelope = json.loads(payload)
        except json.JSONDecodeError:
            return [{"action": "periodic_sync", "reason": "invalid_payload"}]

        event_type = envelope.get("type", "")
        inner_payload = envelope.get("payload", {})

        if event_type in {"ai.memory.sync.request", "ai.memory.bootstrap"}:
            return [{"action": "sync_memory", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.memory.query.request":
            return [{"action": "query_memory", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.learning.ingest":
            return [{"action": "ingest_knowledge", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.learning.dataset_gen":
            return [{"action": "generate_dataset", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.learning.consolidate":
            return [{"action": "consolidate_knowledge", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.learning.extract":
            return [{"action": "extract_knowledge", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.tool.request_3d":
            return [{"action": "tool_request_3d", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.tool.request_2d":
            return [{"action": "tool_request_2d", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.tool.convert":
            return [{"action": "tool_convert", "reason": event_type, "payload": inner_payload}]
        if event_type == "ai.tool.analyze_drawing":
            return [{"action": "tool_analyze_drawing", "reason": event_type, "payload": inner_payload}]
        return []
