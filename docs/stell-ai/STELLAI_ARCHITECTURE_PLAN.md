# STELL-AI Architecture

## Overview
STELL-AI is the intelligence authority of the STELLCODEX platform.
It runs as a single FastAPI service (`runtime_app/`) that exposes
deterministic plan, analyze, decide, and memory endpoints.

The architecture is composed of three layers:

1. Route / Endpoint Layer
2. Intelligence Logic (classifiers, decision engine, analysis builders)
3. Memory and Persistence (PostgreSQL via SQLAlchemy)

## Current Runtime

The active runtime is a single-process FastAPI application.
There is no multi-agent framework, no agent event bus, and no
orchestration layer in this repository.

Implemented endpoints:
- POST /plan — task planning from prompt and optional file context
- POST /analyze — engineering analysis of a file via backend context
- POST /decide — deterministic decision authority with rule explanations
- POST /memory/write — persist task experience to experience_ledger
- POST /memory/search — ILIKE text search over experience_ledger
- GET /capabilities — declared capability surface
- GET /health — liveness probe

## Intelligence Components

MfgClassifier (`lib/mfg_classifier.py`)
Pure-Python heuristic engine. Classifies manufacturing process from
geometry metadata. No external dependencies.

WebKnowledge (`lib/web_knowledge.py`)
Web search fallback using DuckDuckGo and Wikipedia APIs.
Called only when include_web_context=true on /analyze.

BackendClient (`lib/backend_client.py`)
HTTP client for retrieving file context and rule config from the
STELLCODEX backend internal API.

## Safety Constraints

- All file_id inputs are validated as UUID or SCX ID format before
  use in backend requests. Path-traversal characters are rejected.
- Memory search queries escape LIKE metacharacters before use in
  ILIKE predicates.
- Decision mode is normalized to one of: brep, mesh_approx, visual_only.
- Rule explanations use canonical severity values: HIGH, MEDIUM, LOW, INFO.

## Aspirational Design Note

A multi-agent architecture with Planner, Executor, Researcher, Retriever,
and Memory Manager agents is documented as a long-term design direction.
It is NOT implemented in this repository. Do not claim closure of that
architecture without verified code evidence.
