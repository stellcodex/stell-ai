# STELL.AI

Canonical intelligence authority for STELLCODEX.

## Role in System

STELL.AI is the decision and intelligence layer of the STELLCODEX ecosystem.

It is responsible for:
- planning
- analysis
- deterministic decision support
- memory read/write
- intelligence-side retrieval

## System Position

- STELLCODEX → product/workflow surface  
- STELL.AI → intelligence authority  
- ORCHESTRA → execution authority  
- INFRA → runtime infrastructure  

## Canonical Runtime

- `runtime_app/`
- `Dockerfile`

The STELLCODEX backend consumes STELL.AI over HTTP.  
Final intelligence logic is not owned by backend.

## Rules

- do not move execution logic here
- do not mix orchestration responsibilities
- keep intelligence boundary clean

## Repository Notes

- `runtime_app/` is the only active service runtime in this repo
- historical support trees were removed during canonical lock
- this repo is no longer boundary-only

## Related

- `stellcodex/stellcodex`
- `stellcodex/orchestra`
- `stellcodex/infra`
- `stellcodex/stell-assistant`
