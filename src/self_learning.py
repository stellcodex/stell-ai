from __future__ import annotations

from datetime import datetime, timezone
import json
import random
import re
from pathlib import Path
from typing import Any
from textwrap import dedent

from .config import DATASETS_DIR, INCIDENTS_DIR, KNOWLEDGE_BASE_DIR, PENDING_KNOWLEDGE_DIR, QUERY_LOG_PATH, SOLVED_CASES_DIR


def _timestamp_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class KnowledgeIngester:
    def __init__(self, category: str = "engineering", pending: bool = False) -> None:
        self.pending = pending
        if pending:
            self.root = PENDING_KNOWLEDGE_DIR
        else:
            self.root = KNOWLEDGE_BASE_DIR / category
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, title: str, content: str, metadata: dict[str, Any] | None = None) -> Path:
        status = "pending" if self.pending else "validated"
        path = self.root / f"{_timestamp_prefix()}_{title.lower().replace(' ', '_')}.md"
        header = f"# {title}\n"
        header += f"status: {status}\n"
        if metadata:
            header += f"metadata: {json.dumps(metadata, ensure_ascii=True)}\n"
        path.write_text(f"{header}\n{content}\n", encoding="utf-8")
        return path


class ApprenticeQuestionEngine:
    def __init__(self) -> None:
        self.categories = ["engineering", "manufacturing", "cad_cam", "materials", "design"]

    def generate_question(self, context: dict[str, Any]) -> str:
        # Simple heuristic-based question generation for the "Apprentice" persona
        # In a full LLM flow, this would be a prompt to the model.
        
        last_action = context.get("last_action", "analysis")
        target = context.get("target", "system")
        
        templates = [
            f"{target} için en kritik teknik kısıt nedir?",
            f"Bu {target} tasarımında montaj sırasını etkileyen özel bir durum var mı?",
            f"Kullanılan malzemelerin (örneğin {context.get('material', 'mevcut malzeme')}) seçim kriteri nedir?",
            "Bu çözümde gelecekte karşılaşılabilecek en büyük risk nedir?",
            "Benzer bir problemle karşılaştığımızda hangi 'solved_case' referans alınmalı?"
        ]
        return random.choice(templates)


class KnowledgeExtractor:
    def __init__(self) -> None:
        self.query_log = QUERY_LOG_PATH

    def extract_from_logs(self) -> list[dict[str, Any]]:
        if not self.query_log.exists():
            return []
            
        insights = []
        with self.query_log.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    log = json.loads(line)
                    query = log.get("query", "").lower()
                    # Heuristic: Find queries that look like "how to" or "what is" or contain technical terms
                    if any(kw in query for kw in ["nasil", "nedir", "how to", "what is", "standart"]):
                        insights.append({
                            "source_query": log["query"],
                            "potential_answer": log["results"][0]["content"] if log.get("results") else "N/A",
                            "timestamp": log["timestamp"]
                        })
                except Exception:
                    continue
        return insights


class KnowledgeConsolidator:
    def __init__(self) -> None:
        self.cases_dir = SOLVED_CASES_DIR

    def consolidate(self) -> dict[str, Any]:
        cases = list(self.cases_dir.glob("*.md"))
        if len(cases) < 5:
            return {"status": "skipped", "reason": "not_enough_cases"}

        # Heuristic: If multiple cases mention the same "material" or "component", propose a rule
        # In a full flow, this would use LLM clustering.
        proposals = []
        
        # Mock clustering logic for demonstration
        proposals.append({
            "type": "new_truth_proposal",
            "rule": "CNC machining for Alüminyum 7075 always requires coolant type X-22.",
            "evidence": [c.name for c in cases[:3]],
            "confidence": 0.85
        })
        
        return {
            "status": "ok",
            "proposals": proposals,
            "cases_analyzed": len(cases)
        }


def generate_dataset(limit: int = 1000) -> Path:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    dataset_path = DATASETS_DIR / f"training_{_timestamp_prefix()}.jsonl"
    count = 0

    with dataset_path.open("w", encoding="utf-8") as f:
        # 1. From Solved Cases
        for p in SOLVED_CASES_DIR.glob("*.md"):
            try:
                content = p.read_text(encoding="utf-8")
                # Flexible split using regex to handle variations in newlines
                parts = re.split(r"\n+(?:problem|plan|commands|result):\n+", content)
                if len(parts) >= 5:
                    entry = {
                        "instruction": f"Solve this problem: {p.name}",
                        "input": parts[1].strip(),
                        "output": parts[4].strip(),
                    }
                    f.write(json.dumps(entry, ensure_ascii=True) + "\n")
                    count += 1
            except Exception:
                continue

        # 2. From Query Logs
        if QUERY_LOG_PATH.exists():
            with QUERY_LOG_PATH.open("r", encoding="utf-8") as ql:
                for line in ql:
                    if count >= limit:
                        break
                    try:
                        log = json.loads(line)
                        if log.get("results"):
                            entry = {
                                "instruction": log["query"],
                                "input": "",
                                "output": log["results"][0].get("content", ""),
                            }
                            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
                            count += 1
                    except Exception:
                        continue

    return dataset_path


def write_solved_case(name: str, problem: str, plan: str, commands: str, result: str) -> Path:
    SOLVED_CASES_DIR.mkdir(parents=True, exist_ok=True)
    path = SOLVED_CASES_DIR / f"{_timestamp_prefix()}_{name}.md"
    content = dedent(
        f"""\
        # Solved Case

        problem:
        {problem}

        plan:
        {plan}

        commands:
        {commands}

        result:
        {result}
        """
    )
    path.write_text(content, encoding="utf-8")
    return path


def write_incident(name: str, failure: str, root_cause: str, fix_attempt: str) -> Path:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = INCIDENTS_DIR / f"{_timestamp_prefix()}_{name}.md"
    content = dedent(
        f"""\
        # Incident

        failure:
        {failure}

        root cause:
        {root_cause}

        fix attempt:
        {fix_attempt}
        """
    )
    path.write_text(content, encoding="utf-8")
    return path
