from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from runtime_app.lib.backend_client import get_file_context, get_rule_config
from runtime_app.lib.db import db_session
from runtime_app.lib.ids import normalize_scx_id
from runtime_app.lib.mfg_classifier import classify_manufacturing_process
from runtime_app.lib.web_knowledge import search_technical_references

app = FastAPI(title="STELL.AI", version="1.0")

FALLBACK_CONFLICT_FLAG = "decision_fallback_used"


class PlanIn(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)
    file_id: str | None = None


class AnalyzeIn(BaseModel):
    file_id: str = Field(min_length=4, max_length=64)
    include_web_context: bool = False
    web_query: str | None = Field(default=None, max_length=240)


class DecideIn(BaseModel):
    file_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=128)
    mode: str | None = Field(default=None, max_length=48)
    rule_version: str | None = Field(default=None, max_length=48)
    geometry_meta: dict[str, Any] | None = None
    dfm_findings: dict[str, Any] | None = None


class MemoryWriteIn(BaseModel):
    task_query: str = Field(min_length=2, max_length=500)
    successful_plan: dict[str, Any] = Field(default_factory=dict)
    lessons_learned: str | None = Field(default=None, max_length=4000)
    feedback_from_owner: str | None = Field(default=None, max_length=4000)


class MemorySearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=240)
    limit: int = Field(default=5, ge=1, le=20)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decision_mode(mode: str | None) -> str:
    token = str(mode or "").strip().lower()
    if token == "brep":
        return "brep"
    if token == "mesh_approx":
        return "mesh_approx"
    return "visual_only"


def _severity_for_decision(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"blocking", "high"}:
        return "HIGH"
    if token in {"warning", "medium"}:
        return "MEDIUM"
    if token == "low":
        return "LOW"
    return "INFO"


def _manufacturing_method_from_process(process: str) -> str:
    token = str(process or "").strip().lower()
    if token in {"cnc_turning", "cnc_milling"}:
        return "cnc"
    if token == "3d_printing":
        return "3d_printing"
    return "unknown"


def _session_risk_flags(decision_json: dict[str, Any] | None) -> list[str]:
    payload = decision_json if isinstance(decision_json, dict) else {}
    flags = payload.get("conflict_flags")
    if not isinstance(flags, list):
        return []
    seen: set[str] = set()
    items: list[str] = []
    for item in flags:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        items.append(token)
    return items


def _default_explanation() -> dict[str, Any]:
    return {
        "rule_id": "R00_DEFAULT",
        "triggered": False,
        "severity": "INFO",
        "reference": "rule_configs:default",
        "reasoning": "Deterministic decision completed without blocking findings.",
    }


def _fallback_explanation() -> dict[str, Any]:
    return {
        "rule_id": "FALLBACK_NO_MATCH",
        "triggered": True,
        "severity": "WARNING",
        "reference": "rule_configs:fallback",
        "reasoning": "Fallback was used because explicit geometry or DFM evidence was incomplete.",
    }


def _decision_json(
    *,
    mode: str | None,
    rule_version: str,
    geometry_meta: dict[str, Any] | None = None,
    dfm_findings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = _normalize_decision_mode(mode)
    geometry = geometry_meta if isinstance(geometry_meta, dict) else {}
    findings = dfm_findings.get("findings") if isinstance(dfm_findings, dict) else None
    risk_flags = [
        str(item)
        for item in (dfm_findings.get("risk_flags") if isinstance(dfm_findings, dict) else [])
        if str(item or "").strip()
    ]

    process = classify_manufacturing_process(geometry)
    confidence = float(process.confidence or 0.0)
    if normalized_mode == "visual_only" and not geometry:
        confidence = 0.0
    elif normalized_mode == "visual_only":
        confidence = min(max(confidence, 0.1), 0.5)
    else:
        confidence = min(max(confidence, 0.1), 1.0)

    explanations: list[dict[str, Any]] = []
    if isinstance(findings, list):
        for item in findings:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "RULE").strip().upper()
            message = str(item.get("message") or "Deterministic rule triggered.").strip()
            explanations.append(
                {
                    "rule_id": code,
                    "triggered": True,
                    "severity": _severity_for_decision(item.get("severity")),
                    "reference": f"rule_configs:{code.lower()}",
                    "reasoning": message or "Deterministic rule triggered.",
                }
            )

    fallback_used = not geometry and not explanations
    if fallback_used and FALLBACK_CONFLICT_FLAG not in risk_flags:
        risk_flags.append(FALLBACK_CONFLICT_FLAG)

    return {
        "rule_version": str(rule_version or "v0.0"),
        "mode": normalized_mode,
        "confidence": round(confidence, 4),
        "manufacturing_method": _manufacturing_method_from_process(process.process),
        "rule_explanations": explanations or [_fallback_explanation() if fallback_used else _default_explanation()],
        "conflict_flags": _session_risk_flags({"conflict_flags": risk_flags}),
    }


def _meta(context: dict[str, Any]) -> dict[str, Any]:
    payload = context.get("meta")
    return payload if isinstance(payload, dict) else {}


def _assembly_summary(context: dict[str, Any]) -> dict[str, Any]:
    meta = _meta(context)
    tree = meta.get("assembly_tree")
    if not isinstance(tree, list):
        tree = []

    def count_nodes(nodes: list[Any]) -> int:
        total = 0
        for node in nodes:
            if not isinstance(node, dict):
                continue
            total += 1
            children = node.get("children")
            if isinstance(children, list):
                total += count_nodes(children)
        return total

    return {
        "node_count": count_nodes(tree),
        "root_count": len([item for item in tree if isinstance(item, dict)]),
        "tree": [item for item in tree if isinstance(item, dict)],
    }


def _build_engineering_analysis(
    context: dict[str, Any],
    *,
    include_web_context: bool = False,
    web_query: str | None = None,
) -> dict[str, Any]:
    meta = _meta(context)
    geometry = meta.get("geometry_meta_json") if isinstance(meta.get("geometry_meta_json"), dict) else {}
    geometry_report = meta.get("geometry_report") if isinstance(meta.get("geometry_report"), dict) else {}
    dfm_findings = meta.get("dfm_findings") if isinstance(meta.get("dfm_findings"), dict) else {}
    bbox = geometry.get("bbox") if isinstance(geometry.get("bbox"), dict) else {}
    holes = geometry.get("holes") if isinstance(geometry.get("holes"), list) else []
    threads = geometry.get("has_threads")
    part_count = meta.get("part_count") if isinstance(meta.get("part_count"), int) else geometry.get("part_count")
    report_geometry = geometry_report.get("geometry") if isinstance(geometry_report.get("geometry"), dict) else {}
    findings = dfm_findings.get("findings") if isinstance(dfm_findings.get("findings"), list) else []

    recommendations: list[str] = []
    if str(context.get("kind") or "") == "3d" and not context.get("gltf_key"):
        recommendations.append("Missing GLTF derivative: re-run conversion pipeline.")
    if str(context.get("kind") or "") == "archive" and not isinstance(meta.get("archive_manifest_key"), str):
        recommendations.append("Archive manifest missing: re-run archive processing.")
    if str(dfm_findings.get("status_gate") or "").strip().upper() == "NEEDS_APPROVAL":
        recommendations.append("Manufacturing review required due to DFM blockers.")
    if not recommendations:
        recommendations.append("Model is analyzable and ready for downstream workflows.")

    web_context = []
    if include_web_context:
        q = (web_query or str(context.get("original_filename") or "") or "engineering reference").strip()
        try:
            web_context = search_technical_references(q, max_results=5)
        except HTTPError:
            web_context = []

    return {
        "file_id": normalize_scx_id(str(context.get("file_id") or "")),
        "filename": context.get("original_filename"),
        "content_type": context.get("content_type"),
        "status": context.get("status"),
        "kind": context.get("kind"),
        "mode": context.get("mode"),
        "geometry": {
            "units": geometry.get("units") or "unknown",
            "bbox": bbox,
            "diagonal": geometry.get("diagonal"),
            "part_count": int(part_count) if isinstance(part_count, int) else None,
            "hole_count": len([item for item in holes if isinstance(item, dict)]),
            "threads_detected": bool(threads) if isinstance(threads, bool) else None,
        },
        "assembly": _assembly_summary(context),
        "manufacturing": {
            "status_gate": dfm_findings.get("status_gate") if isinstance(dfm_findings.get("status_gate"), str) else "UNKNOWN",
            "risk_flags": dfm_findings.get("risk_flags") if isinstance(dfm_findings.get("risk_flags"), list) else [],
            "wall_mm_min": report_geometry.get("wall_mm_min"),
            "wall_mm_max": report_geometry.get("wall_mm_max"),
            "draft_deg_min": report_geometry.get("draft_deg_min"),
            "has_undercut": report_geometry.get("has_undercut"),
            "findings": findings,
        },
        "features": {
            "holes": holes,
            "surface_breakdown": geometry.get("surfaces") if isinstance(geometry.get("surfaces"), dict) else {},
            "complexity": geometry.get("complexity") if isinstance(geometry.get("complexity"), dict) else {},
        },
        "recommendations": recommendations,
        "web_context": web_context,
        "generated_at": _now().isoformat(),
    }


def _memory_write(data: MemoryWriteIn) -> dict[str, Any]:
    identifier = str(uuid4())
    with db_session() as db:
        db.execute(
            text(
                """
                INSERT INTO experience_ledger (
                  id,
                  task_query,
                  successful_plan,
                  lessons_learned,
                  feedback_from_owner,
                  created_at
                )
                VALUES (
                  :id,
                  :task_query,
                  CAST(:successful_plan AS JSONB),
                  :lessons_learned,
                  :feedback_from_owner,
                  NOW()
                )
                """
            ),
            {
                "id": identifier,
                "task_query": data.task_query,
                "successful_plan": json.dumps(data.successful_plan, ensure_ascii=True),
                "lessons_learned": data.lessons_learned,
                "feedback_from_owner": data.feedback_from_owner,
            },
        )
        db.commit()
    return {"id": identifier, "status": "stored", "stored_at": _now().isoformat()}


def _memory_search(data: MemorySearchIn) -> dict[str, Any]:
    with db_session() as db:
        rows = db.execute(
            text(
                """
                SELECT
                  id,
                  task_query,
                  successful_plan,
                  lessons_learned,
                  feedback_from_owner,
                  created_at
                FROM experience_ledger
                WHERE task_query ILIKE :query
                   OR COALESCE(lessons_learned, '') ILIKE :query
                   OR COALESCE(feedback_from_owner, '') ILIKE :query
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"query": f"%{data.query.strip()}%", "limit": data.limit},
        ).mappings()
        items = [
            {
                "id": str(row["id"]),
                "task_query": row["task_query"],
                "successful_plan": row["successful_plan"] if isinstance(row["successful_plan"], dict) else {},
                "lessons_learned": row["lessons_learned"],
                "feedback_from_owner": row["feedback_from_owner"],
                "created_at": row["created_at"].isoformat() if row["created_at"] is not None else None,
            }
            for row in rows
        ]
    return {"query": data.query, "items": items, "total": len(items)}


def _log_decision(*, project_id: str, mode: str | None, decision: dict[str, Any]) -> None:
    with db_session() as db:
        db.execute(
            text(
                """
                INSERT INTO decision_logs (
                  decision_id,
                  prompt,
                  lane,
                  executor,
                  decision_json,
                  created_at
                )
                VALUES (
                  :decision_id,
                  :prompt,
                  :lane,
                  :executor,
                  CAST(:decision_json AS JSONB),
                  NOW()
                )
                """
            ),
            {
                "decision_id": str(uuid4()),
                "prompt": f"mode={_normalize_decision_mode(mode)} project={project_id}",
                "lane": "stell_ai",
                "executor": "stell_ai_service",
                "decision_json": json.dumps(decision, ensure_ascii=True),
            },
        )
        db.commit()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "OK", "mode": "ACTIVE", "service": "STELL.AI"}


@app.post("/plan")
def plan(data: PlanIn):
    analysis = None
    if data.file_id:
        context = get_file_context(data.file_id, include_assembly_tree=True)
        analysis = _build_engineering_analysis(context)

    steps = [
        "Collect relevant file and project context.",
        "Evaluate deterministic geometry and DFM evidence.",
        "Decide the next execution action with traceable rules.",
        "Persist lessons if operator feedback arrives.",
    ]
    if analysis is not None and analysis.get("manufacturing", {}).get("status_gate") == "NEEDS_APPROVAL":
        steps.insert(3, "Hold for approval because deterministic blockers are present.")
    return {
        "status": "OK",
        "mode": "ACTIVE",
        "prompt": data.prompt,
        "file_id": data.file_id,
        "plan": steps,
        "analysis": analysis,
        "generated_at": _now().isoformat(),
    }


@app.post("/analyze")
def analyze(data: AnalyzeIn):
    context = get_file_context(data.file_id, include_assembly_tree=True)
    return _build_engineering_analysis(context, include_web_context=data.include_web_context, web_query=data.web_query)


@app.post("/decide")
def decide(data: DecideIn):
    context = get_file_context(data.file_id, include_assembly_tree=False) if data.file_id else None
    meta = _meta(context or {})
    geometry_meta = data.geometry_meta if isinstance(data.geometry_meta, dict) else (
        meta.get("geometry_meta_json") if isinstance(meta.get("geometry_meta_json"), dict) else None
    )
    dfm_findings = data.dfm_findings if isinstance(data.dfm_findings, dict) else (
        meta.get("dfm_findings") if isinstance(meta.get("dfm_findings"), dict) else None
    )
    mode = data.mode or (str(context.get("mode")) if isinstance((context or {}).get("mode"), str) else None)
    project_id = data.project_id or (str((context or {}).get("project_id") or "default"))
    rule_info = get_rule_config(project_id=project_id)
    rule_version = str(data.rule_version or rule_info.get("rule_version") or "v0.0")

    decision = _decision_json(
        mode=mode,
        rule_version=rule_version,
        geometry_meta=geometry_meta,
        dfm_findings=dfm_findings,
    )
    _log_decision(project_id=project_id, mode=mode, decision=decision)
    return {
        **decision,
        "project_id": project_id,
        "file_id": str((context or {}).get("file_id") or data.file_id or ""),
    }


@app.post("/memory/write")
def memory_write(data: MemoryWriteIn):
    return _memory_write(data)


@app.post("/memory/search")
def memory_search(data: MemorySearchIn):
    return _memory_search(data)


@app.get("/capabilities")
def capabilities():
    return {
        "platform": "STELL.AI",
        "mode": "ACTIVE",
        "modules": [
            "Planning",
            "Deterministic Engineering Analysis",
            "Decision Authority",
            "Memory Write/Search",
            "Evidence-Aware Research",
        ],
        "generated_at": _now().isoformat(),
    }
