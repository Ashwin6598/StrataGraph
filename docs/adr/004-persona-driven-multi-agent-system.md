# ADR-004: Persona-Driven Multi-Agent Architecture

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Agent Interaction Layer (`codegraph/tools/`, `prompts/`)

---

## Context
CodeGraph addresses two vastly different user groups with conflicting communication requirements:
1. **Product Managers / Business Stakeholders:** They do not understand programming languages, syntax, or stack traces. They need answers in plain business English, percentage compliance metrics, and scenario simulations.
2. **Software Engineers / SREs:** They need deep technical diagnostics, exact file paths, line ranges, error codes, ADR citations, and diff analysis.

Building two entirely separate backend servers would duplicate logic and fracture the shared knowledge graph.

## Decision
1. **Shared Tool Server with Persona-Specific Partitioning:**
   - Maintain a single MCP server exposing 15 tools across 4 categories:
     - **Product Tools:** `query_prd_coverage`, `simulate_scenario`, `get_change_history`, `list_uncovered_requirements`
     - **Developer Tools:** `debug_issue`, `check_safe_to_change`, `get_function_lineage`, `review_pr_diff`, `cross_org_bug_check`
     - **Shared Exploration:** `search_graph`, `get_related_entities`, `explain_traversal`
     - **Ingestion & Mutations:** `ingest_*`, `record_bugfix`
2. **Client-Side Persona System Prompts:**
   - Supply ready-to-use system prompts in [`prompts/product-persona.md`](file:///Users/ashwin/Documents/Projects/GraphHack/prompts/product-persona.md) and [`prompts/developer-persona.md`](file:///Users/ashwin/Documents/Projects/GraphHack/prompts/developer-persona.md).
   - Also register them directly via `@server.prompt` in MCP 2.x (`product_advisor` and `developer_assistant`).
3. **Strict Presentation Boundaries:**
   - Product tools MUST format results in plain English, business metrics, and guardrail terms, actively suppressing code syntax.
   - Developer tools MUST return exact line ranges, file paths, and ADR invariant citations.

## Consequences
- **Positive:**
  - One server, one unified graph, zero duplicated database connections.
  - Allows seamless persona switching: a PM in Claude Desktop uses the Product prompt, while an engineer in Cursor uses the Developer prompt against the exact same graph.
- **Negative:**
  - If a client fails to set a system prompt, the LLM might call tools across both categories indiscriminately.
- **Invariants:**
  - Product persona responses MUST NEVER output code snippets or raw programming syntax.
  - Developer persona responses MUST cite governing ADR IDs before approving or rejecting code modifications.
