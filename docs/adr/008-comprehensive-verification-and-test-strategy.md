# ADR-008: Comprehensive Verification & Test Strategy

**ADR ID:** `ADR-008`  
**Title:** Comprehensive Verification & Test Strategy  
**Status:** `ACCEPTED`  
**Date:** `2026-10-17`  
**Author:** CodeGraph Architecture Working Group  

---

## Context
CodeGraph integrates four distinct domain entity chains (CodeBase, PRD, ADR, Operations) and exposes them through 17 Model Context Protocol (MCP) tools and 2 persona prompts. In local development and enterprise CI/CD environments alike, testing graph tooling poses unique challenges:
1. Docker or cloud graph databases (e.g. FalkorDB) might not be running in all local developer environments or lightweight CI runners.
2. Complex mocking frameworks introduce fragility and false confidence.
3. Both persona behavioral constraints (e.g. Product Manager plain English output vs. Developer technical diagnostics) must be strictly verified.
4. Mutation workflows, such as human-in-the-loop bugfix approvals, must be deterministically checked.

## Decision
We establish a zero-external-dependency, modular test architecture powered by `pytest` and `anyio`:
1. **Hierarchical Test Suite Structure:**
   - `tests/test_db_engine.py`: Tests `LocalMemoryGraph` and dual-driver graph engine CRUD, persistence, and neighbor traversal.
   - `tests/test_parsers.py`: Tests standard library AST parsing, PRD/ADR markdown extraction, and runbook incident ingestion.
   - `tests/test_product_tools.py`: Tests PRD requirement coverage calculation, plain English scenario simulation with stopword filtering, change history date filtering, and uncovered requirement gap analysis.
   - `tests/test_developer_tools.py`: Tests log diagnostics matching, safe-to-change constraint checks, 4-pillar lineage tracing, PR diff safety checks, and cross-organizational incident search.
   - `tests/test_shared_and_ingest.py`: Tests global graph search, N-hop neighborhood expansion, ASCII traversal explanation, directory ingestion, and human approval workflow gating.
   - `tests/test_mcp_server.py`: Tests asynchronous MCP 2.x server initialization, tool registration (all 17 tools), persona prompt generation, and direct tool execution.
   - `tests/test_cli.py`: Tests Click-based CLI commands (`status`, `demo`, `seed`, `help`) via `CliRunner`.
   - `test_codegraph.py`: Root end-to-end integration test runner validating end-to-end system cohesion.
2. **Offline Local Engine Test Execution:** Tests run against `LocalMemoryGraph` with automatic session seeding via `tests/conftest.py`, running in under 0.5 seconds without Docker.
3. **Behavioral Invariant Testing:** Product persona outputs are tested for absence of raw code and presence of business concepts; Developer persona outputs are tested for line numbers, ADR IDs, and safety constraint warnings.

## Consequences

### Positive Impact
- **Ultra-Fast Feedback:** The entire 48-test suite runs in under 0.5 seconds.
- **Zero Mock Overhead:** Tests run against the real graph engine logic rather than brittle function mocks.
- **Complete Test Matrix:** Full coverage across CLI, database, parsers, product tools, developer tools, shared tools, ingestion pipelines, and MCP server.

### Tradeoffs
- Tests against live FalkorDB require a reachable Redis/FalkorDB instance; in its absence, tests seamlessly run against `LocalMemoryGraph`.

## Architectural Invariants
1. `TEST_EXECUTION_TIME < 2.0s`: Full test suite must execute in under 2 seconds.
2. `ZERO_EXTERNAL_CONTAINER_DEPENDENCY`: Tests must pass in environments without Docker or network access.
3. `PERSONA_CONTRACT_COMPLIANCE`: Product tools must never leak code snippets; Developer tools must always provide file/line/ADR anchors.
