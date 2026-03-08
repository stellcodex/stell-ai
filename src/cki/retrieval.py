from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import math


@dataclass
class CKIChunk:
    artifact_id: str
    drive_path: str
    chunk_id: str
    chunk_text: str
    embedding_vector: list[float]
    source_link: str
    ingested_at: str


class CKIRetriever:
    """Rebuildable retrieval client over CKI export files."""

    def __init__(self, index_path: str | Path):
        self.index_path = Path(index_path)

    def _load(self) -> list[CKIChunk]:
        if not self.index_path.exists():
            return []
        raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        out: list[CKIChunk] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            out.append(
                CKIChunk(
                    artifact_id=str(item.get("artifact_id") or ""),
                    drive_path=str(item.get("drive_path") or ""),
                    chunk_id=str(item.get("chunk_id") or ""),
                    chunk_text=str(item.get("chunk_text") or ""),
                    embedding_vector=[float(v) for v in (item.get("embedding_vector") or []) if isinstance(v, (int, float))],
                    source_link=str(item.get("source_link") or ""),
                    ingested_at=str(item.get("ingested_at") or ""),
                )
            )
        return out

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        an = math.sqrt(sum(x * x for x in a))
        bn = math.sqrt(sum(y * y for y in b))
        if an <= 0 or bn <= 0:
            return 0.0
        return dot / (an * bn)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        chunks = self._load()
        scored: list[tuple[float, CKIChunk]] = []
        for chunk in chunks:
            score = self._cosine(query_embedding, chunk.embedding_vector)
            scored.append((score, chunk))
        scored.sort(key=lambda row: row[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, chunk in scored[: max(1, top_k)]:
            out.append(
                {
                    "score": round(score, 6),
                    "artifact_id": chunk.artifact_id,
                    "drive_path": chunk.drive_path,
                    "chunk_id": chunk.chunk_id,
                    "chunk_text": chunk.chunk_text,
                    "source_link": chunk.source_link,
                    "ingested_at": chunk.ingested_at,
                }
            )
        return out
