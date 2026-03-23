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
- canonical image entrypoint: `Dockerfile`

The STELLCODEX backend consumes this service over HTTP. Backend does not own final intelligence logic.

## Repository notes

- `runtime_app/` is the only active service runtime in this repo
- historical support trees were removed during canonical lock
- this repo is no longer boundary-only
