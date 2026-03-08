from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .config import INGEST_REPORT_PATH, QUERY_LOG_PATH, SOURCE_MANIFEST_PATH
from .sources import build_chunks, build_source_manifest


def run_ingest(reason: str = "manual") -> dict[str, Any]:
    manifest = build_source_manifest()
    if SOURCE_MANIFEST_PATH.exists() and INGEST_REPORT_PATH.exists():
        previous_manifest = json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        if previous_manifest == manifest:
            previous_report = json.loads(INGEST_REPORT_PATH.read_text(encoding="utf-8"))
            previous_report.update(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": reason,
                    "status": "skipped_unchanged",
                }
            )
            INGEST_REPORT_PATH.write_text(json.dumps(previous_report, indent=2), encoding="utf-8")
            return previous_report

    chunks = build_chunks()
    from .memory import StellHybridMemory

    memory = StellHybridMemory()
    try:
        stats = memory.rebuild(chunks)
    finally:
        memory.close()
    by_type = Counter(chunk.doc_type for chunk in chunks)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "status": "rebuilt",
        "indexed_chunks": stats["indexed_chunks"],
        "indexed_sources": stats["indexed_sources"],
        "by_doc_type": dict(by_type),
        "sample_sources": sorted({chunk.source_path for chunk in chunks})[:20],
    }
    INGEST_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    SOURCE_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return report


def log_query(query: str, results: list[dict[str, Any]]) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "results": results,
    }
    with QUERY_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
