from __future__ import annotations

from typing import Any

from .config import TOP_K_DEFAULT
from .ingest import log_query, run_ingest
from .memory import LiveContextManager, StellHybridMemory
from .self_learning import (
    ApprenticeQuestionEngine,
    KnowledgeConsolidator,
    KnowledgeExtractor,
    KnowledgeIngester,
    generate_dataset,
)
from .tools import StellToolAwareness


class Executor:
    def __init__(self) -> None:
        pass

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        kind = action.get("action")
        if kind == "sync_memory":
            report = run_ingest(reason=action.get("reason", "event"))
            return {"action": kind, "status": "ok", "report": report}

        if kind == "query_memory":
            payload = action.get("payload", {})
            query = payload.get("query", "")
            top_k = int(payload.get("top_k", TOP_K_DEFAULT))
            with StellHybridMemory() as memory:
                results = memory.retrieve(query, top_k=top_k)
            log_query(query, results)
            return {"action": kind, "status": "ok", "query": query, "results": results}

        if kind == "ingest_knowledge":
            payload = action.get("payload", {})
            category = payload.get("category", "engineering")
            title = payload.get("title", "unnamed")
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
            pending = bool(payload.get("pending", False))
            ingester = KnowledgeIngester(category=category, pending=pending)
            path = ingester.store(title, content, metadata=metadata)
            return {"action": kind, "status": "ok", "path": str(path)}

        if kind == "generate_dataset":
            payload = action.get("payload", {})
            limit = int(payload.get("limit", 1000))
            path = generate_dataset(limit=limit)
            return {"action": kind, "status": "ok", "path": str(path)}

        if kind == "generate_learning_question":
            payload = action.get("payload", {})
            engine = ApprenticeQuestionEngine()
            question = engine.generate_question(payload)
            return {"action": kind, "status": "ok", "question": question}

        if kind == "consolidate_knowledge":
            payload = action.get("payload", {})
            engine = KnowledgeConsolidator()
            result = engine.consolidate()
            return {"action": kind, "status": "ok", "result": result}

        if kind == "extract_knowledge":
            payload = action.get("payload", {})
            engine = KnowledgeExtractor()
            insights = engine.extract_from_logs()
            return {"action": kind, "status": "ok", "insights": insights}

        if kind == "sync_context":
            payload = action.get("payload", {})
            key = payload.get("key", "last_event")
            value = payload.get("value", {})
            mgr = LiveContextManager()
            mgr.update_learning_state(key, value)
            return {"action": kind, "status": "ok"}

        if kind == "tool_request_3d":
            payload = action.get("payload", {})
            tools = StellToolAwareness()
            event_id = tools.request_3d_metadata(payload.get("file_path", ""))
            return {"action": kind, "status": "sent", "event_id": event_id}

        if kind == "tool_request_2d":
            payload = action.get("payload", {})
            tools = StellToolAwareness()
            event_id = tools.request_2d_metadata(payload.get("file_path", ""))
            return {"action": kind, "status": "sent", "event_id": event_id}

        if kind == "tool_convert":
            payload = action.get("payload", {})
            tools = StellToolAwareness()
            event_id = tools.trigger_conversion(
                payload.get("source_path", ""),
                payload.get("target_format", payload.get("target_format", "glb"))
            )
            return {"action": kind, "status": "sent", "event_id": event_id}

        if kind == "tool_analyze_drawing":
            payload = action.get("payload", {})
            tools = StellToolAwareness()
            event_id = tools.analyze_drawing(payload.get("file_path", ""))
            return {"action": kind, "status": "sent", "event_id": event_id}

        if kind == "periodic_sync":
            report = run_ingest(reason=action.get("reason", "periodic"))
            return {"action": "sync_memory", "status": "ok", "report": report}

        return {"action": kind or "unknown", "status": "skipped"}
