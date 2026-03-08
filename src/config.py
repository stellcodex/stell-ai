from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_ROOT = Path("/root/workspace")
TRUTH_DIR = WORKSPACE_ROOT / "_truth"
HANDOFF_DIR = WORKSPACE_ROOT / "handoff"
KNOWLEDGE_DIR = WORKSPACE_ROOT / "_knowledge"
RUNS_DIR = WORKSPACE_ROOT / "_runs"
BACKUPS_DIR = WORKSPACE_ROOT / "_backups"

SOLVED_CASES_DIR = KNOWLEDGE_DIR / "solved_cases"
INCIDENTS_DIR = KNOWLEDGE_DIR / "incidents"
KNOWLEDGE_BASE_DIR = KNOWLEDGE_DIR / "knowledge"
PENDING_KNOWLEDGE_DIR = KNOWLEDGE_DIR / "pending"
DATASETS_DIR = WORKSPACE_ROOT / "_packages" / "datasets" / "stell_ai_v1"
MEMORY_DIR = KNOWLEDGE_DIR / "memory"
VECTOR_STORE_DIR = MEMORY_DIR / "qdrant_store"
BM25_STATE_PATH = MEMORY_DIR / "bm25_state.json"
SOURCE_MANIFEST_PATH = MEMORY_DIR / "source_manifest.json"
INGEST_REPORT_PATH = RUNS_DIR / "stell_ai_ingest_report.json"
DAEMON_LOG_PATH = RUNS_DIR / "stell_ai_ingest_daemon.log"
QUERY_LOG_PATH = RUNS_DIR / "stell_ai_query_log.jsonl"

RAG_EVAL_REPORT_PATH = HANDOFF_DIR / "RAG_EVAL_REPORT.json"

COLLECTION_NAME = "stell_ai_memory"
EMBEDDING_MODEL_NAME = os.getenv("STELL_AI_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE = int(os.getenv("STELL_AI_CHUNK_SIZE", "20000"))
CHUNK_OVERLAP = int(os.getenv("STELL_AI_CHUNK_OVERLAP", "800"))
SYNC_INTERVAL_SECONDS = int(os.getenv("STELL_AI_SYNC_INTERVAL_SECONDS", "300"))
TOP_K_DEFAULT = int(os.getenv("STELL_AI_TOP_K", "5"))
QDRANT_LOCK_WAIT_SECONDS = float(os.getenv("STELL_AI_QDRANT_LOCK_WAIT_SECONDS", "60"))
QDRANT_LOCK_POLL_SECONDS = float(os.getenv("STELL_AI_QDRANT_LOCK_POLL_SECONDS", "0.25"))

REDIS_URL = os.getenv("STELL_AI_REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM_KEY = os.getenv("STELL_AI_STREAM_KEY", "stell:events:stream")
CONSUMER_GROUP = os.getenv("STELL_AI_CONSUMER_GROUP", "intelligence")
CONSUMER_NAME = os.getenv("STELL_AI_CONSUMER_NAME", "stell-ai-intelligence")


def ensure_directories() -> None:
    for path in [
        SOLVED_CASES_DIR,
        INCIDENTS_DIR,
        MEMORY_DIR,
        VECTOR_STORE_DIR,
        RUNS_DIR,
        HANDOFF_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
