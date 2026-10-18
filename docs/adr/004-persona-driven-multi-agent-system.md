# ADR-004: Persona-Driven Multi-Agent Architecture

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Agent Interaction Layer (`codegraph/tools/`, `prompts/`)

---

## Context
CodeGraph addresses three vastly different user groups with conflicting communication and operational requirements:
1. **Product Managers / Business Stakeholders:** They do not read code syntax or AST definitions. They require answers in plain business English, percentage compliance metrics, scenario simulations, and PRD Owner governance.
2. **Software Engineers / SREs:** They need deep technical diagnostics, exact file paths, line ranges, error codes, ADR citations, regression analysis, and Code Domain Owner signoff.
3. **Technical Program Managers (TPMs) / Agile Delivery Leads:** They require delivery velocity metrics, sprint burndown, cycle time analytics, root-cause PRD-to-code bottleneck diagnosis, and cross-team capability unlocking across all domain services.

Building separate backend servers would duplicate logic and fracture the shared knowledge graph.

## Decision
1. **Shared Tool Server with Persona-Specific Partitioning:**
   - Maintain a single MCP server exposing 26 tools across 5 categories:
     - **Product Tools:** `query_prd_coverage`, `simulate_scenario`, `get_change_history`, `list_uncovered_requirements`, `update_prd_features_and_scenarios`, `approve_prd_update_via_email`
     - **Developer Tools:** `debug_issue`, `check_safe_to_change`, `get_function_lineage`, `review_pr_diff`, `cross_org_bug_check`
     - **Program Manager Tools:** `query_program_delivery_status`, `diagnose_delivery_bottlenecks`, `unlock_cross_team_capabilities`, `get_feature_lead_time_metrics`, `trace_requirement_to_delivery_chain`, `ingest_jira_board`
     - **Shared Exploration:** `search_graph`, `get_related_entities`, `explain_traversal`
     - **Ingestion & Mutations:** `ingest_codebase`, `ingest_prd`, `ingest_adr`, `ingest_runbook`, `record_bugfix`, `approve_bugfix_via_email`
2. **Client-Side Persona System Prompts:**
   - Supply ready-to-use system prompts in [`prompts/product-persona.md`](../../prompts/product-persona.md), [`prompts/developer-persona.md`](../../prompts/developer-persona.md), and [`prompts/program-persona.md`](../../prompts/program-persona.md).
   - Also register them directly via `@server.prompt` in MCP (`product_advisor`, `developer_assistant`, `program_manager`).
3. **Strict Presentation Boundaries & Roles/Responsibilities:**
   - Product persona MUST format results in plain English, business metrics, and guardrail terms, actively suppressing code syntax.
   - Developer persona MUST return exact line ranges, file paths, and ADR invariant citations.
   - Program Manager persona MUST communicate in agile velocity terms, story points, cycle times, blockers, and cross-team synergy, avoiding raw AST snippets.

## Consequences
- **Positive:**
  - One server, one unified graph, zero duplicated database connections.
  - Allows seamless persona switching: a PM in Claude Desktop uses the Product prompt, an engineer in Cursor uses the Developer prompt, and a TPM uses the Program prompt against the exact same graph.
- **Negative:**
  - If a client fails to set a system prompt, the LLM might call tools across categories indiscriminately.
- **Invariants:**
  - Product persona responses MUST NEVER output code snippets or raw programming syntax.
  - Developer persona responses MUST cite governing ADR IDs before approving or rejecting code modifications.
  - Program persona responses MUST cite story points, assignees, cycle times, and cross-domain pattern reuse opportunities.
