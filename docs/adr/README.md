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
| [**ADR-011**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/011-domain-owner-email-approval-and-ingestion-flow.md) | Code Domain Owner Email Approval & Ingestion Workflow | Approval & Notification Layer (`codegraph/approval_service.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-012**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/012-project-entity-dual-ownership-model.md) | Project Entity Dual-Ownership Model (Codebase & PRD Owner) | Root Anchor Schema (`codegraph/schema.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-013**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/013-prd-agent-updates-and-owner-approval-workflow.md) | PRD Agent Updates and PRD Owner Email Approval Workflow | Product Governance & Staged Ingestion (`codegraph/tools/product_tools.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-014**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/014-program-manager-persona-and-agile-execution-flow.md) | Program Manager Persona & Agile Execution Flow (5th Pillar) | Delivery Intelligence & Jira Ingestion (`codegraph/tools/program_tools.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-015**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/015-cross-team-capability-unlocking-and-domain-synergy.md) | Cross-Team Capability Unlocking & Domain Synergy Architecture | Delivery Acceleration & Cross-Team Synergy (`codegraph/tools/program_tools.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-016**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/016-role-based-access-control-and-architectural-governance.md) | Role-Based Access Control (RBAC) and Architectural Governance | IAM & Governance (`codegraph/iam.py`, `codegraph/tools/architect_tools.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-017**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/017-agent-security-harness-and-ingestion-guardrails.md) | Agent Security Harness and Ingestion Guardrails | Security & Ingestion Guardrails (`codegraph/guardrails.py`, `codegraph/tools/ingest_tools.py`) | `ACCEPTED` | 2026-10-18 |
| [**ADR-018**](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/018-falkordb-graphblas-performance-optimization.md) | FalkorDB GraphBLAS Performance Optimization & High-Throughput Cypher Execution | Database & Performance Engine (`codegraph/db.py`, `codegraph/tools/`) | `ACCEPTED` | 2026-10-18 |

---

> *Note: For the sample payment gateway demo dataset used during hackathon presentations, see [demo_data/adr/](file:///Users/ashwin/Documents/Projects/GraphHack/demo_data/adr/).*
