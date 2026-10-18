# ADR-001: FalkorDB Graph Engine Architecture

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Database & Storage Layer (`codegraph/db.py`)

---

## Context
CodeGraph requires ultra-low-latency traversals across heterogeneous entities (AST code hierarchies, functional requirements, architectural invariants, incident records, and temporal change records). Traditional relational databases require expensive recursive JOINs, while pure vector embeddings lack deterministic path explainability and structural edge-traversal guarantees.

## Decision
1. **FalkorDB as Core Graph Database:**
   - Use FalkorDB as the primary graph database engine. Built on GraphBLAS sparse matrices, FalkorDB evaluates multi-hop OpenCypher queries with sub-millisecond latency.
   - All mutations and reads use standardized OpenCypher statements (`MERGE`, `MATCH`, `RETURN`).
2. **Unified GraphDatabase Interface:**
   - The application layer interacts solely with the unified `GraphDatabase` singleton. Tool modules never make direct network assumptions about raw socket protocols.
3. **GraphBLAS Optimization and Plan Caching (ADR-018):**
   - Incorporate explicit single-property indexing (`CREATE INDEX FOR (n:Label) ON (n.prop)`) across 24 core entities, string interning (`intern($val)`) for repeated enum attributes, explicit sparse matrix node labels, and parameterized query execution to maximize query plan caching and minimize RAM overhead.

## Consequences
- **Positive:**
  - Enables sub-millisecond multi-hop reasoning over complex call chains and requirement trees.
  - High concurrency and sub-millisecond execution powered by GraphBLAS sparse matrix multiplications and plan caching.
  - Transparent deployment to enterprise FalkorDB Cloud via environment variables.
- **Negative:**
  - Requires maintaining disciplined schema and index definitions for GraphBLAS matrix sparsity.
- **Invariants:**
  - Database calls MUST always return explainable Cypher query strings and traversal paths.
  - Graph mutations and traversals MUST adhere to the GraphBLAS optimization rules detailed in [**ADR-018**](018-falkordb-graphblas-performance-optimization.md).

