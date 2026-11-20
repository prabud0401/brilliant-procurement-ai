# 2. PostgreSQL with pgvector for Relational and Vector Storage

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
The application manages relational procurement entities (purchase requests, quotes, purchase orders, approval steps, audit logs) while also requiring vector embeddings for semantic search over extracted document chunks (Q&A assistant). Introducing a dedicated external vector database (such as Pinecone, Qdrant, or Azure AI Search) introduces operational overhead, extra cost, and dual-write consistency issues.

## Decision
Use PostgreSQL 16 with the `pgvector` extension as the single unified data store for both relational procurement records and 1536-dimensional chunk embeddings. Perform hybrid search by combining pgvector cosine distance queries with PostgreSQL full-text search (`tsvector`) via Reciprocal Rank Fusion (RRF).

## Consequences
- **Positive:** Single database to back up, migrate (via Alembic), and secure; transactional consistency across business entities and vector chunks; zero additional cloud service costs; robust row-level security and permission filtering directly in SQL.
- **Negative:** Scaling vector search independently of relational tables requires tuning PostgreSQL shared memory and indexes (`ivfflat` or `hnsw`); compute-heavy vector operations share resources with relational transactions.
