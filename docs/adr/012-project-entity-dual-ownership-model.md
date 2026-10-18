# ADR-012: Project Entity Dual-Ownership Model (Codebase Owner & PRD Owner)

**ADR ID:** `ADR-012`  
**Title:** Project Entity Dual-Ownership Model (Codebase Owner & PRD Owner)  
**Status:** `ACCEPTED`  
**Date:** `2026-10-18`  
**Author:** CodeGraph Architecture Working Group  
**Component:** `codegraph/schema.py`, `codegraph/ingest/pipeline.py`, `codegraph/__main__.py`

---

## Context
CodeGraph anchors all enterprise institutional knowledge (CodeBase, PRD, ADR, Operations) to a root **`Project`** node in FalkorDB.

In real-world enterprise engineering, project ownership is inherently bi-directional:
1. **The Product Discipline (PRD Owner):** Owns business viability, feature roadmaps, functional requirements, compliance guardrails, and acceptance test scenarios.
2. **The Engineering Discipline (Codebase Owner):** Owns repository architecture, coding standards, AST integrity, dependency health, and operational resilience.

Without explicit ownership recorded directly on the root `Project` node, autonomous agents auditing the graph cannot determine the appropriate human point of contact when:
- PRD coverage falls below target thresholds (escalate to PRD Owner).
- Architectural invariants or security guardrails are violated in a PR (escalate to Codebase Owner).
- Incident postmortems require domain-level reviews.

## Decision

We establish a first-class **Dual-Ownership Model** directly on the root `Project` entity:

1. **Schema Enhancement (`codegraph/schema.py`):**
   Extend `ProjectNode` with two mandatory, typed ownership attributes:
   - `codebase_owner: str` (e.g. `payment-tech-lead@payflow.internal`)
   - `prd_owner: str` (e.g. `product-lead@payflow.internal`)

2. **Unified Pipeline & Ingestion Invariants (`codegraph/ingest/pipeline.py`):**
   - `IngestionPipeline` accepts explicit `codebase_owner` and `prd_owner` arguments during initialization.
   - Falls back to configured environment defaults (`CODEBASE_OWNER`, `PRD_OWNER`) in `codegraph/config.py`.
   - Ingests the root `(:Project)` node with both owner attributes populated in FalkorDB.

3. **CLI & Operational Exposure (`codegraph/__main__.py`):**
   - The CLI `codegraph ingest` command exposes `--codebase-owner` and `--prd-owner` flags.
   - The CLI `codegraph status` command queries and displays the Project Name, Codebase Owner, and PRD Owner alongside database connection health.

4. **Seed Dataset Alignment (`seed.py`):**
   - The PayFlow demonstration dataset is seeded with:
     - `codebase_owner = "payment-tech-lead@payflow.internal"`
     - `prd_owner = "product-lead@payflow.internal"`

## Consequences

### Positive Impact
- **Symmetric Accountability:** Mirrors the two-persona agent architecture (`Product Advisor` aligns with PRD Owner; `Developer Assistant` aligns with Codebase Owner).
- **Automated Escalation:** Automated CI/CD actions and MCP tools can tag and notify the respective owners based on whether an issue is business/requirement-related or technical/architectural.
- **Explainability:** Cypher queries starting from `(:Project)` immediately surface domain leadership without consulting external directories.

### Tradeoffs
- None. Adds two lightweight string attributes to the root graph node with zero traversal performance penalty.

## Architectural Invariants
1. `PROJECT_OWNERSHIP_INTEGRITY`: Every `Project` node in FalkorDB must possess valid non-empty `codebase_owner` and `prd_owner` properties.
2. `PERSONA_ALIGNMENT`: Tool diagnostics for Product Managers report to `prd_owner`; engineering safety verdicts report to `codebase_owner`.
