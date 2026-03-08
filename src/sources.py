from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    HANDOFF_DIR,
    INCIDENTS_DIR,
    KNOWLEDGE_BASE_DIR,
    PENDING_KNOWLEDGE_DIR,
    RUNS_DIR,
    SOLVED_CASES_DIR,
    TRUTH_DIR,
)

TEXT_FILE_SUFFIXES = {".md", ".txt", ".log", ".json"}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
CANONICAL_TRUTH_FILE = re.compile(r"^\d{2}_.+\.md$")
EXCLUDED_RUN_LOG_NAMES = {
    "audit.log",
    "codex_execution.log",
    "stell_ai_ingest_daemon.log",
    "stell_ai_ingest_report.json",
}
EXCLUDED_HANDOFF_NAMES = {
    "LIVE-CONTEXT.json",
    "RAG_EVAL_REPORT.json",
    "SESSION-2026-03-04.md",
    "codex-status.md",
    "gemini-status.md",
    "judge-last-decision.json",
    "stell-ai-v8-5-final-consolidation-complete-autonomy-achieved-status.md",
    "stell-judge-status.md",
}


@dataclass
class SourceChunk:
    chunk_id: str
    source_path: str
    title: str
    doc_type: str
    chunk_index: int
    chunk_count: int
    content: str
    sha256: str
    modified_at: float

    def to_payload(self) -> dict:
        return asdict(self)


def iter_source_files() -> Iterable[tuple[str, Path]]:
    directories = [
        ("truth", TRUTH_DIR),
        ("handoff", HANDOFF_DIR),
        ("solved_case", SOLVED_CASES_DIR),
        ("incident", INCIDENTS_DIR),
        ("knowledge", KNOWLEDGE_BASE_DIR),
        ("pending", PENDING_KNOWLEDGE_DIR),
        ("run_log", RUNS_DIR),
    ]
    for doc_type, root in directories:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
                continue
            if doc_type == "truth" and (path.parent != TRUTH_DIR or not CANONICAL_TRUTH_FILE.match(path.name)):
                continue
            if doc_type == "handoff" and path.name in EXCLUDED_HANDOFF_NAMES:
                continue
            if doc_type == "run_log" and path.name in EXCLUDED_RUN_LOG_NAMES:
                continue
            yield doc_type, path


def build_source_manifest() -> dict[str, float]:
    manifest: dict[str, float] = {}
    for _, path in iter_source_files():
        manifest[str(path)] = path.stat().st_mtime
    return manifest


def load_text(path: Path) -> str:
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            return json.dumps(payload, indent=2, ensure_ascii=True)
        except json.JSONDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size * 2:
        return [normalized]
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalized) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= chunk_size:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            end = min(len(paragraph), start + chunk_size)
            chunk = paragraph[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(paragraph):
                break
            start = max(0, end - overlap)
        current = ""
    if current:
        chunks.append(current)
    return chunks


def build_chunks() -> list[SourceChunk]:
    output: list[SourceChunk] = []
    for doc_type, path in iter_source_files():
        text = load_text(path)
        chunks = chunk_text(text)
        modified_at = path.stat().st_mtime
        for index, chunk in enumerate(chunks):
            sha = hashlib.sha256(f"{path}:{index}:{chunk}".encode("utf-8")).hexdigest()
            output.append(
                SourceChunk(
                    chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}:{index}:{sha}")),
                    source_path=str(path),
                    title=path.name,
                    doc_type=doc_type,
                    chunk_index=index,
                    chunk_count=len(chunks),
                    content=chunk,
                    sha256=sha,
                    modified_at=modified_at,
                )
            )
    return output


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
