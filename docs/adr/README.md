# 🏛️ CodeGraph Architecture Decision Records (ADRs)

This directory documents all foundational architectural decisions made for the **CodeGraph** platform. Each record details the context, architectural decision, consequences, and invariants for a specific component.

---

## Index of Architectural Decisions

| ADR ID | Title | Component | Status | Date |
|---|---|---|---|---|
| [**ADR-001**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/001-falkordb-graph-engine-and-offline-fallback.md) | FalkorDB Graph Engine and Offline Fallback Architecture | Database & Storage Layer (`codegraph/db.py`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-002**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/002-four-pillar-graph-data-model.md) | Four-Pillar Connected Knowledge Graph Data Model | Schema & Domain Model (`codegraph/schema.py`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-003**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/003-mcp-server-as-universal-agent-interface.md) | Model Context Protocol (MCP) as Universal Agent Interface | Interface Layer (`codegraph/mcp_server.py`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-004**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/004-persona-driven-multi-agent-system.md) | Persona-Driven Multi-Agent Architecture | Tool & Persona Layer (`codegraph/tools/`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-005**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/005-deterministic-ast-and-document-ingestion.md) | Deterministic AST and Markdown Ingestion Pipeline | Ingestion Pipeline (`codegraph/ingest/`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-006**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/006-human-in-the-loop-approval-workflow.md) | Human-in-the-Loop Quality Approval Gate for Operations | Operational Mutations (`codegraph/tools/ingest_tools.py`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-007**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/007-dual-transport-deployment-strategy.md) | Dual-Transport Deployment Strategy (Stdio vs HTTP) | Transport & Deployment Layer (`codegraph/config.py`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-008**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/008-comprehensive-verification-and-test-strategy.md) | Comprehensive Verification & Test Strategy | Quality & Test Suite (`tests/`) | `ACCEPTED` | 2026-10-17 |
| [**ADR-009**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/009-unified-production-ingestion-pipeline.md) | Unified Production Ingestion Pipeline & Auto-Linker | Production Ingestion (`codegraph/ingest/pipeline.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-010**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/010-multi-format-enterprise-document-and-polyglot-ingestion.md) | Multi-Format Enterprise Document & Polyglot Ingestion Adapter | Multi-Format Adapter (`codegraph/ingest/document_converter.py`) | `ACCEPTED` | 2026-10-18 |

---

> *Note: For the sample payment gateway demo dataset used during hackathon presentations, see [demo_data/adr/](file:///Users/ashwin/Documents/Projects/GraphHack/demo_data/adr/).*
