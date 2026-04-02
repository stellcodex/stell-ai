# Retrieval Layer Specification

## Current Implementation

The retrieval layer is implemented as a lightweight web search fallback.
There is no vector database, no embedding pipeline, and no multi-source
indexing in this repository.

Implemented retrieval (`lib/web_knowledge.py`):
- DuckDuckGo Instant Answer API — primary source
- Wikipedia OpenSearch API — fallback
- Called only from /analyze when include_web_context=true
- Timeout: 6 seconds, max 5 results per call
- Results are deduplicated by URL before return

## Aspirational Design (not yet implemented)

The following pipeline is described as a long-term design direction.
It is NOT implemented in this repository. Do not claim closure without
verified code evidence.

Designed data sources:
- Google Drive artifacts
- GitHub repositories
- Internal STELLCODEX artifacts
- User uploaded files

Designed pipeline:
1. Convert query to embedding
2. Perform vector similarity search
3. Filter results by tenant and permissions
4. Assemble contextual knowledge block
5. Return context to agent runtime

Designed storage:
- Vector embeddings in a vector database
- Metadata and access control in PostgreSQL

## Security

Current retrieval makes outbound HTTPS calls only to:
- api.duckduckgo.com
- en.wikipedia.org

The query string is caller-controlled but sent only to these
external public APIs. Internal service addresses are not reachable
through the current retrieval path.

When the full retrieval pipeline is implemented, all retrieval
operations must enforce tenant isolation and permission validation
before any results are returned.
