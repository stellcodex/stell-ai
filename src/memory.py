from __future__ import annotations

import os
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from .config import (
    BM25_STATE_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    HANDOFF_DIR,
    QDRANT_LOCK_POLL_SECONDS,
    QDRANT_LOCK_WAIT_SECONDS,
    TOP_K_DEFAULT,
    VECTOR_STORE_DIR,
    ensure_directories,
)
from .sources import SourceChunk, tokenize

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
_MODEL_CACHE: dict[str, SentenceTransformer] = {}
RANK_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
RANK_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "how",
    "in",
    "is",
    "of",
    "the",
    "to",
    "what",
    "where",
    "which",
}

try:
    import torch

    torch.set_num_threads(int(os.getenv("STELL_AI_TORCH_THREADS", "4")))
    torch.set_num_interop_threads(1)
except Exception:
    torch = None


class LiveContextManager:
    def __init__(self) -> None:
        self.path = HANDOFF_DIR / "LIVE-CONTEXT.json"

    def update_learning_state(self, key: str, value: Any) -> None:
        if not self.path.exists():
            data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        else:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        learning_context = data.setdefault("ai_learning_context", {})
        learning_context[key] = value
        learning_context["last_sync_at"] = datetime.now(timezone.utc).isoformat()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


class StellHybridMemory:
    def __init__(self) -> None:
        ensure_directories()
        self.model = self._load_model()
        self._clear_stale_lock()
        self.client = self._open_client()
        self.collection_name = COLLECTION_NAME
        self._ensure_collection()
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list[dict[str, Any]] = []
        self._load_bm25_state()

    def _load_model(self) -> SentenceTransformer:
        model = _MODEL_CACHE.get(EMBEDDING_MODEL_NAME)
        if model is not None:
            return model
        try:
            model = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=True)
        except OSError as exc:
            raise RuntimeError(
                f"Embedding model '{EMBEDDING_MODEL_NAME}' is not available in local cache."
            ) from exc
        _MODEL_CACHE[EMBEDDING_MODEL_NAME] = model
        return model

    def _open_client(self) -> QdrantClient:
        deadline = time.monotonic() + QDRANT_LOCK_WAIT_SECONDS
        while True:
            try:
                return QdrantClient(path=str(VECTOR_STORE_DIR))
            except RuntimeError as exc:
                if "already accessed by another instance of Qdrant client" not in str(exc):
                    raise
                if time.monotonic() >= deadline:
                    raise
                time.sleep(QDRANT_LOCK_POLL_SECONDS)

    def close(self) -> None:
        client = getattr(self, "client", None)
        if client is not None:
            client.close()

    def __enter__(self) -> "StellHybridMemory":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def _clear_stale_lock(self) -> None:
        lock_path = VECTOR_STORE_DIR / ".lock"
        if not lock_path.exists():
            return
        result = subprocess.run(
            ["pgrep", "-af", "python -m stell_ai"],
            capture_output=True,
            text=True,
            check=False,
        )
        live_lines = [
            line for line in result.stdout.splitlines()
            if line.strip() and str(os.getpid()) not in line
        ]
        if not live_lines:
            lock_path.unlink(missing_ok=True)

    def _ensure_collection(self) -> None:
        collections = {item.name for item in self.client.get_collections().collections}
        if self.collection_name in collections:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.model.get_sentence_embedding_dimension(),
                distance=Distance.COSINE,
            )
        )

    def rebuild(self, chunks: list[SourceChunk]) -> dict[str, Any]:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._ensure_collection()

        if not chunks:
            self._bm25 = BM25Okapi([["empty"]])
            self._bm25_chunks = []
            self._persist_bm25_state()
            return {"indexed_chunks": 0, "indexed_sources": 0}

        embeddings = self.model.encode([chunk.content for chunk in chunks], show_progress_bar=False)
        points = [
            PointStruct(
                id=chunk.chunk_id,
                vector=embeddings[index].tolist(),
                payload=chunk.to_payload(),
            )
            for index, chunk in enumerate(chunks)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

        tokenized = [tokenize(chunk.content) or ["empty"] for chunk in chunks]
        self._bm25 = BM25Okapi(tokenized)
        self._bm25_chunks = [chunk.to_payload() for chunk in chunks]
        self._persist_bm25_state()

        unique_sources = {chunk.source_path for chunk in chunks}
        return {"indexed_chunks": len(chunks), "indexed_sources": len(unique_sources)}

    def retrieve(self, query: str, top_k: int = TOP_K_DEFAULT) -> list[dict[str, Any]]:
        dense_results = self._dense_search(query, top_k=top_k * 3)
        sparse_results = self._sparse_search(query, top_k=top_k * 3)
        query_tokens = self._rank_tokens(query)

        combined: dict[str, dict[str, Any]] = {}
        for rank, item in enumerate(dense_results, start=1):
            payload = combined.setdefault(item["chunk_id"], dict(item))
            payload["dense_rank"] = rank
            payload["dense_score"] = item["dense_score"]
            payload["rrf_score"] = payload.get("rrf_score", 0.0) + (1.0 / (60 + rank))
        for rank, item in enumerate(sparse_results, start=1):
            payload = combined.setdefault(item["chunk_id"], dict(item))
            payload["bm25_rank"] = rank
            payload["bm25_score"] = item["bm25_score"]
            payload["rrf_score"] = payload.get("rrf_score", 0.0) + (1.0 / (60 + rank))

        for item in combined.values():
            item["rrf_score"] = item.get("rrf_score", 0.0) + self._ranking_bonus(item, query_tokens)

        ranked = sorted(combined.values(), key=lambda item: item.get("rrf_score", 0.0), reverse=True)
        return ranked[:top_k]

    def _ranking_bonus(self, item: dict[str, Any], query_tokens: set[str]) -> float:
        bonus = 0.0
        doc_type = item.get("doc_type")
        if doc_type == "truth":
            bonus += 0.005
        elif doc_type == "knowledge":
            bonus += 0.004
        elif doc_type in {"solved_case", "incident"}:
            bonus += 0.002

        title_tokens = self._rank_tokens(item.get("title", ""))
        overlap = query_tokens & title_tokens
        if overlap and query_tokens and title_tokens:
            recall = len(overlap) / len(query_tokens)
            precision = len(overlap) / len(title_tokens)
            f1 = 2 * precision * recall / (precision + recall)
            bonus += 0.03 * f1
            if title_tokens <= query_tokens:
                bonus += 0.004
        return bonus

    def _rank_tokens(self, text: str) -> set[str]:
        normalized = text.lower().replace("_", " ").replace("-", " ")
        tokens: set[str] = set()
        for raw in RANK_TOKEN_PATTERN.findall(normalized):
            if raw.isdigit():
                continue
            if raw == "changelog":
                tokens.update({"change", "log"})
                continue
            if raw.endswith("s") and len(raw) > 4:
                raw = raw[:-1]
            if raw in RANK_STOPWORDS:
                continue
            tokens.add(raw)
        return tokens

    def _dense_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_vector = self.model.encode(query).tolist()
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        output = []
        for result in results:
            payload = dict(result.payload or {})
            payload["chunk_id"] = str(result.id)
            payload["dense_score"] = float(result.score)
            output.append(payload)
        return output

    def _sparse_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not self._bm25 or not self._bm25_chunks:
            return []
        scores = self._bm25.get_scores(tokenize(query) or ["empty"])
        ranked_indexes = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)[:top_k]
        output = []
        for index in ranked_indexes:
            if scores[index] <= 0:
                continue
            payload = dict(self._bm25_chunks[index])
            payload["bm25_score"] = float(scores[index])
            output.append(payload)
        return output

    def _load_bm25_state(self) -> None:
        if not BM25_STATE_PATH.exists():
            return
        payload = json.loads(BM25_STATE_PATH.read_text(encoding="utf-8"))
        self._bm25_chunks = payload.get("chunks", [])
        tokens = payload.get("tokens", [])
        if tokens:
            self._bm25 = BM25Okapi(tokens)

    def _persist_bm25_state(self) -> None:
        tokens = [tokenize(chunk["content"]) or ["empty"] for chunk in self._bm25_chunks]
        payload = {"chunks": self._bm25_chunks, "tokens": tokens}
        BM25_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
