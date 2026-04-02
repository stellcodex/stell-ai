# STELL-AI Agent Runtime

## Current Implementation

STELL-AI runs as a single FastAPI service, not a multi-agent system.
There is no internal event bus, no agent scheduler, and no agent
lifecycle management in this repository.

The "agent runtime" framing below describes a design direction that
is NOT yet implemented. It is preserved here for architectural context.

## Designed Agent Roles (not yet implemented)

Planner — break complex requests into task graphs
Executor — run tool calls and API requests
Researcher — collect knowledge from retrieval layer
Retriever — query external and internal knowledge sources
Memory Manager — maintain session and long-term memory state

## Actual Execution Flow (current)

HTTP request received
→ FastAPI route validates input
→ Optional: fetch file context from backend
→ Intelligence logic runs (classifier, decision engine, or analysis builder)
→ Optional: write or read from experience_ledger (PostgreSQL)
→ Response returned to caller

## Communication

In the current runtime, there is no inter-agent communication.
All logic is in-process within the single FastAPI application.

## Safety

Input validation enforces:
- file_id must be a valid UUID or SCX ID format
- memory search queries escape LIKE metacharacters
- decision mode is normalized before use
- rule explanation severity is constrained to canonical values
