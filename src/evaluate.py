from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import RAG_EVAL_REPORT_PATH
from .ingest import run_ingest
from .memory import StellHybridMemory

BENCHMARKS = [
    {"query": "What is the current overall system state?", "expected_document": "00_SYSTEM_STATE.md"},
    {"query": "How is the event spine defined?", "expected_document": "02_EVENT_SPINE.md"},
    {"query": "What is the STELL-AI operating chain?", "expected_document": "03_STELL_AI_OPERATING_MODEL.md"},
    {"query": "What are the UI console requirements?", "expected_document": "04_UI_CONSOLE_SPEC.md"},
    {"query": "Which API contracts are canonical?", "expected_document": "05_API_CONTRACTS.md"},
    {"query": "What are the data model and storage rules?", "expected_document": "06_DATA_MODEL_AND_STORAGE.md"},
    {"query": "How do backups and Drive sync work?", "expected_document": "07_BACKUP_AND_DRIVE_SYNC.md"},
    {"query": "What is the disaster recovery runbook?", "expected_document": "08_DISASTER_RECOVERY_RUNBOOK.md"},
    {"query": "What are the security and access rules?", "expected_document": "09_SECURITY_AND_ACCESS.md"},
    {"query": "What acceptance tests define success?", "expected_document": "10_ACCEPTANCE_TESTS.md"},
    {"query": "How is the task queue documented?", "expected_document": "11_TASK_QUEUE.md"},
    {"query": "Where are decisions and change log entries stored?", "expected_document": "12_DECISIONS_AND_CHANGELOG.md"},
    {"query": "What is in the archive index?", "expected_document": "13_ARCHIVE_INDEX.md"},
    {"query": "What should the daily report contain?", "expected_document": "14_DAILY_REPORT_TEMPLATE.md"},
    {"query": "How is agent governance described?", "expected_document": "15_AGENT_GOVERNANCE_AND_IDENTITY.md"},
    {"query": "How is the AI engine and training documented?", "expected_document": "15_AI_ENGINE_AND_TRAINING.md"},
    {"query": "What is the live context handoff summary?", "expected_document": "LIVE-CONTEXT.md"},
    {"query": "What problem was solved in the share contract remediation?", "expected_document": "share_contract_remediation.md"},
    {"query": "What incident captured the middleware type error and backend container drift?", "expected_document": "middleware_and_container_sync.md"},
    {"query": "What contract verification evidence exists for file, share, and viewer behavior?", "expected_document": "contracts_verification.md"},
]


def run_evaluation() -> dict:
    run_ingest(reason="evaluation")
    memory = StellHybridMemory()
    results = []
    hits_at_5 = 0

    try:
        for benchmark in BENCHMARKS:
            retrieval = memory.retrieve(benchmark["query"], top_k=5)
            matched_rank = None
            for index, item in enumerate(retrieval, start=1):
                if benchmark["expected_document"] in item.get("source_path", ""):
                    matched_rank = index
                    break
            reciprocal_rank = 0.0 if matched_rank is None else 1.0 / matched_rank
            score = reciprocal_rank
            if matched_rank is not None and matched_rank <= 5:
                hits_at_5 += 1
            results.append(
                {
                    "query": benchmark["query"],
                    "expected_document": benchmark["expected_document"],
                    "retrieval": [
                        {
                            "source_path": item.get("source_path"),
                            "title": item.get("title"),
                            "combined_score": item.get("rrf_score"),
                        }
                        for item in retrieval
                    ],
                    "expected_rank": matched_rank,
                    "score": score,
                }
            )
    finally:
        memory.close()

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_count": len(BENCHMARKS),
        "hit_at_5": hits_at_5,
        "hit_at_5_rate": hits_at_5 / len(BENCHMARKS),
        "mean_reciprocal_rank": sum(item["score"] for item in results) / len(results),
        "results": results,
    }
    RAG_EVAL_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
