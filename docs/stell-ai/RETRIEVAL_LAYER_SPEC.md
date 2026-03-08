# Retrieval Layer Specification

## Purpose
The retrieval layer provides contextual knowledge to STELL-AI
by searching indexed data sources and assembling relevant context
for the reasoning pipeline.

## Data Sources
- Google Drive artifacts
- GitHub repositories
- Internal STELLCODEX artifacts
- User uploaded files

## Retrieval Pipeline
1. Convert query to embedding
2. Perform vector similarity search
3. Filter results by tenant and permissions
4. Assemble contextual knowledge block
5. Return context to agent runtime

## Storage
Vector embeddings are stored in a vector database.
Metadata and access control data are stored in Postgres.

## Security
All retrieval operations enforce:
- tenant isolation
- permission validation
- artifact access control
