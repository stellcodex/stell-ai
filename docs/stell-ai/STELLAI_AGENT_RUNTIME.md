# STELL-AI Agent Runtime

## Agents
Planner
Executor
Researcher
Retriever
Memory Manager

## Execution Flow
User Input
→ Planner builds task graph
→ Executor agents run tasks
→ Retriever gathers context
→ Memory Manager updates state
→ Response returned

## Communication
Agents communicate through an internal event bus.

## Safety
All actions must pass permission validation and tenant isolation.
