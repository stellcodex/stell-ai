# STELL.AI

Canonical owner for STELLCODEX intelligence authority.

## Responsibility

- planning
- analysis
- deterministic decision support
- memory read/write
- intelligence-side retrieval helpers

## Canonical runtime

- authoritative HTTP runtime: `runtime_app/`
- canonical image entrypoint: [`Dockerfile`](/root/workspace/_canonical_repos/stell-ai/Dockerfile)

The STELLCODEX backend consumes this service over HTTP. Backend does not own final intelligence logic.

## Repository notes

- `runtime_app/` is the runtime used by the proven split deployment
- `src/` remains intelligence-owned support code and historical agent tooling
- this repo is no longer boundary-only
