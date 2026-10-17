# ADR-001: FalkorDB Graph Engine and Offline Fallback Architecture

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Database & Storage Layer (`codegraph/db.py`)

---

## Context
CodeGraph requires ultra-low-latency traversals across heterogeneous entities (AST code hierarchies, functional requirements, architectural invariants, incident records, and temporal change records). Traditional relational databases require expensive recursive JOINs, while pure vector embeddings lack deterministic path explainability and structural edge-traversal guarantees.

Furthermore, developers, hackathon judges, and automated test runners need to execute the system locally without being strictly blocked if Docker or external container daemons are not running on their host workstation.

## Decision
1. **FalkorDB as Primary Graph Database:**
   - Use FalkorDB as the primary graph database engine. Built on GraphBLAS sparse matrices, FalkorDB evaluates multi-hop OpenCypher queries with sub-millisecond latency.
   - All mutations and reads use standardized OpenCypher statements (`MERGE`, `MATCH`, `RETURN`).
2. **Deterministic In-Memory & JSON Fallback Engine:**
   - Implement `LocalMemoryGraph` in [`codegraph/db.py`](file:///Users/ashwin/Documents/Projects/GraphHack/codegraph/db.py) with automatic fallback when FalkorDB is unreachable and `FALKORDB_AUTO_FALLBACK=true`.
   - The fallback engine maintains identical property graph semantics, multi-hop BFS neighborhood traversals, and persists state to `codegraph_local_store.json`.
3. **Unified GraphDatabase Interface:**
   - The application layer interacts solely with the unified `GraphDatabase` singleton. Tool modules never make direct network assumptions about FalkorDB vs fallback storage.

## Consequences
- **Positive:**
  - Enables sub-millisecond multi-hop reasoning over complex call chains and requirement trees.
  - Guarantees 100% zero-dependency local execution and offline test passes without Docker.
  - Transparent transition between local in-memory mock and enterprise FalkorDB Cloud via environment variables.
- **Negative:**
  - In-memory fallback does not implement full Cypher grammar beyond the specific pattern matchers and traversals needed by CodeGraph tools.
- **Invariants:**
  - Database calls MUST always return explainable Cypher query strings and traversal paths regardless of the active storage backend.
