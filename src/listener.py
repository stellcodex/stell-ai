from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis

from .config import CONSUMER_GROUP, CONSUMER_NAME, REDIS_URL, STREAM_KEY


class EventListener:
    def __init__(self) -> None:
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.stream_key = STREAM_KEY
        self.group = CONSUMER_GROUP
        self.consumer = CONSUMER_NAME
        self.ensure_group()

    def ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(self.stream_key, self.group, id="$", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def poll(self, block_ms: int = 5000) -> list[tuple[str, dict[str, str]]]:
        response = self.redis.xreadgroup(
            groupname=self.group,
            consumername=self.consumer,
            streams={self.stream_key: ">"},
            count=10,
            block=block_ms,
        )
        if not response:
            return []
        _, messages = response[0]
        return messages

    def ack(self, message_id: str) -> None:
        self.redis.xack(self.stream_key, self.group, message_id)

    def emit(self, event_type: str, payload: dict[str, Any]) -> str:
        envelope = {
            "event_id": payload.get("event_id") or f"stell-ai-{datetime.now(timezone.utc).timestamp()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "stell-ai.memory",
            "type": event_type,
            "payload": payload,
        }
        return self.redis.xadd(self.stream_key, {"payload": json.dumps(envelope, ensure_ascii=True)})
