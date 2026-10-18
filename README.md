# 🧠 CodeGraph: Connected Knowledge Graph for Code, PRD, and ADR

> **Hackathon Track 01: Agents That Act on Connected Data**  
> *Multi-hop reasoning · Graph queries as agent tools · Tool selection through MCP · Actions based on graph data · Explainable results*

---

## 💡 The Problem

1. **The UAT & PRD Verification Bottleneck:**  
   Product Managers create PRDs and hand them off to engineering. When testing features for UAT, product teams cannot verify whether complex edge-case scenarios are guarded in the code without engineering cycles. Every verification requires back-and-forth communication, slowing release velocity.
2. **Knowledge Loss & Blind Overrides:**  
   When developers join a team, they don't know *why* existing code was written—is a specific check due to a PRD requirement, an architectural constraint (ADR), or a past regression fix? Overriding code without this context introduces severe bugs, SLA violations, or financial loss. There is no unified quality lineage.

---

## 🚀 The Solution: CodeGraph

CodeGraph connects **Source Code (AST)**, **Product Requirements (PRD)**, **Architecture Decisions (ADR)**, and **Quality History (Runbooks, BugFixes, RCAs)** into a unified property graph backed by **FalkorDB**.

Instead of a siloed custom UI, CodeGraph is an **MCP (Model Context Protocol) Server**. Any MCP-compatible agent client (**Claude Desktop, Antigravity, Cursor, VS Code Copilot, or CLI**) connects directly to the server.

```
┌─────────────────────────────────────────────────────────────┐
│                     Any MCP Agent Client                    │
│        (Claude Desktop / Antigravity / Cursor / Copilot)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ JSON-RPC (stdio or HTTP/SSE)
┌──────────────────────────────▼──────────────────────────────┐
│                  CodeGraph MCP Server                       │
│  ┌───────────────────────┬───────────────────────────────┐  │
│  │   Product Persona     │       Developer Persona       │  │
│  │  • query_prd_coverage │      • debug_issue            │  │
│  │  • simulate_scenario  │      • check_safe_to_change   │  │
│  │  • get_change_history │      • get_function_lineage   │  │
│  │  • list_uncovered_req │      • review_pr_diff         │  │
│  │  • update_prd_features│      • cross_org_bug_check    │  │
│  │  • approve_prd_update │                               │  │
│  └───────────────────────┴───────────────────────────────┘  │
│  ┌───────────────────────┬───────────────────────────────┐  │
│  │ Program Manager Persona│       Ingestion & Mutations   │  │
│  │  • query_program_stats │      • ingest_code / prd / adr│  │
│  │  • diagnose_bottlenecks│      • ingest_jira_board      │  │
│  │  • get_lead_time_stats │      • record_bugfix (Approval│  │
│  │  • trace_delivery_chain│      • approve_bugfix_email   │  │
│  │  • search_graph        │      • approve_prd_email      │  │
│  └───────────────────────┴───────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                                │ OpenCypher
┌──────────────────────────────▼──────────────────────────────┐
│                    FalkorDB / Graph Store                   │
│                                                             │
│                      [ Root: Project ]                      │
│        ┌───────────┬───────────┬───────────┬───────────┐    │
│        ▼           ▼           ▼           ▼           ▼    │
│     [ PRD ]     [ ADR ]   [ CodeBase ]   [ Ops ]   [ Agile ]│
│        │           │           │           │           │    │
│      Input     Requirement    Input      Issues       Epic  │
│        │           │           │           │           │    │
│  Functional Req Architecture Logic Flow   RCA        Feature│
│        │           │           │           │           │    │
│   Guardrails    Decisions   Classes       Fix         Story │
│        │           │           │           │           │    │
│     Output      Result     Functions    Result     Developer│
│        ▲           ▲           │           ▲           │    │
│        │           │      Code Logic       │           │    │
│        │           │           │           │           │    │
│        │           │        Output         │           │    │
│        └───────────┴───────────┴───────────┴───────────┘    │
│                                                             │
│   [ Timeline & History: ChangeTimeline (What & Why) ]      │
└─────────────────────────────────────────────────────────────┘
```

### 🔗 The 5-Pillar Connected Data Model

All entities stem from **`Project`** (which explicitly records the **`codebase_owner`** and **`prd_owner`**) and are interconnected across their lifecycle:

1. **CodeBase Chain:** `Project` ➔ `CodeInput` ➔ `LogicFlow` ➔ `Class` ➔ `Function` ➔ `CodeLogic` ➔ `CodeOutput`
2. **PRD Chain:** `Project` ➔ `PRDInput` ➔ `FunctionalRequirement` ➔ `Guardrail` ➔ `PRDOutput`
3. **ADR Chain:** `Project` ➔ `ADRRequirement` ➔ `Architecture` ➔ `Decision` ➔ `ADRResult`
4. **Operations Chain:** `Project` ➔ `Issue` ➔ `RCA` ➔ `Fix` ➔ `OpResult`
5. **Program Flow Chain (Agile / Jira Execution):** `Project` ➔ `Epic` ➔ `AgileFeature` ➔ `Story` ➔ `Developer / AST Function`
6. **Timeline & History:** `ChangeTimeline` records **WHAT** changed and **WHY** it changed, linked to `FunctionalRequirement`, `Decision`, `Fix`, and commits.

#### Dual-Ownership Model on `Project`:
* **`codebase_owner`** (e.g., `payment-tech-lead@payflow.internal`): Escalation lead for architectural constraints, AST breaks, and code regressions.
* **`prd_owner`** (e.g., `product-lead@payflow.internal`): Escalation lead for requirement coverage gaps, agile deliverables, and business guardrail failures.

#### Cross-Entity Interlinks:
* **Code is built from ADR:** `Decision` ➔ `CONSTRAINS_FUNCTION` / `ENFORCED_IN_CODE_LOGIC` ➔ `Function` / `CodeLogic`
* **ADR is built from PRD:** `FunctionalRequirement` ➔ `DRIVES_ADR_REQUIREMENT` ➔ `ADRRequirement`, `Guardrail` ➔ `JUSTIFIES_DECISION` ➔ `Decision`
* **Code implements PRD:** `FunctionalRequirement` ➔ `IMPLEMENTED_BY_FUNCTION` ➔ `Function`, `Guardrail` ➔ `VERIFIED_BY_LOGIC` ➔ `CodeLogic`
* **Program Flow realizes PRD:** `AgileFeature` / `Story` ➔ `REALIZES_REQUIREMENT` ➔ `FunctionalRequirement`
* **Program Flow executes Code:** `Story` ➔ `IMPLEMENTS_CODE` ➔ `Function`, `Story` ➔ `ASSIGNED_TO_DEVELOPER` ➔ Developer
* **Program Flow guided by Architecture:** `AgileFeature` ➔ `GUIDED_BY_ARCHITECTURE` ➔ `Architecture` / `Decision`
* **Operations fixes the CodeBase & Program:** `Issue` ➔ `MANIFESTED_IN_FUNCTION`, `Issue` ➔ `VIOLATED_DECISION`, `Fix` ➔ `MODIFIES_CODE_LOGIC` / `FIXES_FUNCTION`, `Story` ➔ `RESOLVES_ISSUE` ➔ `Issue`


---

## ⚡ Quick Start (Local Run in 60 Seconds)

### 1. Prerequisites & Environment Setup
Clone the repository and set up a virtual environment (Python 3.10+):

```bash
git clone https://github.com/your-org/GraphHack.git
cd GraphHack

# Create virtualenv using uv or standard python
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 2. Run Database (Optional / Automatic)
CodeGraph connects to **FalkorDB** on `localhost:6379`. If you have Docker installed:

```bash
docker compose up -d
# Opens FalkorDB on port 6379 and FalkorDB Browser at http://localhost:3000
```

> **Zero-Dependency Resilience:** If Docker is not running on your machine, CodeGraph automatically switches to its built-in deterministic local graph store (`codegraph_local_store.json`), allowing full offline testing, development, and judging without external dependencies!

### 3. Seed Demo Data
Build the PayFlow payment gateway knowledge graph:

```bash
python seed.py
# Or via CLI:
python -m codegraph seed
```

### 4. Verify & Run Live CLI Demo
Run an end-to-end self-check demonstrating both Product and Developer scenarios with Cypher queries and explainable paths:

```bash
python -m codegraph demo
```

---

## 🔌 Connecting to MCP Clients

Add CodeGraph to your favorite agent client configuration.

### A. Claude Desktop
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "/absolute/path/to/GraphHack/.venv/bin/python",
      "args": ["-m", "codegraph", "serve"],
      "env": {
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379"
      }
    }
  }
}
```

### B. Antigravity (AGY)
Add to `~/.gemini/settings.json` or your project `.gemini/settings.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "/absolute/path/to/GraphHack/.venv/bin/python",
      "args": ["-m", "codegraph", "serve"],
      "env": {
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379"
      }
    }
  }
}
```

### C. Cursor / VS Code Copilot
Add to `.cursor/mcp.json` or VS Code MCP settings:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "/absolute/path/to/GraphHack/.venv/bin/python",
      "args": ["-m", "codegraph", "serve"],
      "env": {
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379"
      }
    }
  }
}
```

---

## 🎭 Three Personas, One Connected Graph

| Persona | System Prompt | Communication Style | Primary Tools |
|---------|---------------|---------------------|---------------|
| **Product Manager** | `prompts/product-persona.md` | Plain English, business terms, completion %, zero code | `query_prd_coverage`, `simulate_scenario`, `get_change_history`, `list_uncovered_requirements`, `update_prd_features_and_scenarios`, `approve_prd_update_via_email` |
| **Developer / SRE** | `prompts/developer-persona.md` | Technical, file paths, line numbers, ADR constraints | `debug_issue`, `check_safe_to_change`, `get_function_lineage`, `review_pr_diff`, `cross_org_bug_check` |
| **Program Manager** | `prompts/program-persona.md` | Delivery velocity, story points, sprint burndown, cycle times, blockers | `query_program_delivery_status`, `diagnose_delivery_bottlenecks`, `get_feature_lead_time_metrics`, `trace_requirement_to_delivery_chain`, `ingest_jira_board` |

---

## 🎬 Hackathon Demo Scenarios

### Scenario 1: Product PRD Compliance Check
- **User Prompt:** *"How close is our code to the PayFlow PRD?"*
- **Agent Action:** Calls `query_prd_coverage()`.
- **Agent Output (Plain English):**
  > "The codebase is currently **80.0% compliant** with the PayFlow PRD (8 of 10 requirements implemented). 2 requirements remain unimplemented:
  > • **REQ-004:** Multi-Currency Dynamic Currency Conversion (DCC)
  > • **REQ-008:** Partial Refund Support"

### Scenario 2: Business Scenario Simulation
- **User Prompt:** *"What happens if a customer attempts to pay with an expired card?"*
- **Agent Action:** Calls `simulate_scenario("expired card")`.
- **Agent Output:**
  > "When a card with a past expiration date is submitted, the system checks the card during pre-validation (`REQ-002: Expiry & Luhn Card Validation`). The transaction is rejected with error `CARD_EXPIRED` before contacting payment networks, resulting in zero bank clearing fees."

### Scenario 3: Incident Debugging & Root Cause Analysis (RCA)
- **User Prompt:** *"We're seeing `REFUND_TIMEOUT` alerts on `/v1/refunds`. What's causing this?"*
- **Agent Action:** Calls `debug_issue("REFUND_TIMEOUT")`.
- **Agent Output (Technical):**
  > "🚨 **Matched Incident: BUG-342**  
  > • **Root Cause Analysis (RCA):** `RefundProcessor.WORKER_POOL_CONCURRENCY` was reduced from 5 to 2. At concurrency 2, queue lag exceeds 120s under peak loads (>80 req/s), triggering 504 Gateway Timeouts.  
  > • **Target Location:** `demo_data/code/refund_processor.py` (lines 42-56)  
  > • **Resolution Procedure:** Open `refund_processor.py` and restore `WORKER_POOL_CONCURRENCY = 5` per `ADR-002`."

### Scenario 4: Safety Audit for New Developers
- **User Prompt:** *"I'm a new engineer. Is it safe for me to reduce the retry attempts in `fraud_detector.py`?"*
- **Agent Action:** Calls `check_safe_to_change("retry_with_backoff")`.
- **Agent Output:**
  > "⚠️ **VERDICT: UNSAFE / STRICT CONSTRAINTS**  
  > **Target:** `fraud_detector.py:retry_with_backoff`  
  > • **Architectural Constraint (`ADR-001`):** Mandates exactly 3 retries with exponential backoff. Developers are strictly forbidden from lowering retry counts as it violates card network SLAs.  
  > • **Past Regression Bugs:** Changes to this function previously caused **BUG-112** (packet drop false declines) and **BUG-298**."

### Scenario 5: Program Delivery Status & Root-Cause Bottleneck Diagnosis
- **User Prompt:** *"Where are the actual delivery bottlenecks between our PRD requirements and engineering code?"*
- **Agent Action:** Calls `diagnose_delivery_bottlenecks()`.
- **Agent Output (Program Manager Terms):**
  > "📊 **Program Delivery Status: 69.0% completion** (29 of 42 story points delivered across 3 Epics).  
  > 🚨 **2 Delivery Bottlenecks Identified:**  
  > 1. **[Active Blocker] REQ-008 (Partial Refund Support):** Halted on ticket `PAY-307` assigned to Sarah Jenkins in Sprint 25. Reason: *Awaiting legal & accounting clearance on merchant interchange fee clawback accounting rule.*  
  > 2. **[Definition Gap] REQ-004 (Dynamic Currency Conversion):** Stalled in backlog; ticket `PAY-306` is unassigned and not committed to any active engineering sprint."

---

## 🚢 Production Deployment

Moving from local hackathon testing to enterprise cloud production requires **zero code changes**:

### 1. Ingest Any Real Repository & Documentation
Use the unified production ingestion pipeline to index an arbitrary codebase, PRDs, ADRs, and git history into FalkorDB:

```bash
uv run python -m codegraph ingest \
  --project-name "BillingService" \
  --project-id "project:billing" \
  --code ./src \
  --prd ./docs/prd \
  --adr ./docs/adr \
  --runbooks ./docs/runbooks \
  --git .
```

The pipeline supports all enterprise documentation formats via [`DocumentConverter`](file:///Users/ashwin/Documents/Projects/GraphHack/codegraph/ingest/document_converter.py):
* **Markdown (`.md`, `.markdown`):** Native PRD and ADR format
* **Plain Text (`.txt`):** Unstructured notes and specifications
* **HTML / Confluence (`.html`, `.htm`):** Confluence wiki exports parsed via stdlib HTML parser
* **JSON / Jira (`.json`):** Jira issue exports and OpenAPI / Swagger specifications
* **PDF (`.pdf`):** Extracted via system `pdftotext` or `pypdf`
* **Word (`.docx`):** Extracted via native macOS `textutil` or `python-docx`

The **Auto-Linker** automatically inspects function docstrings and git commits to synthesize cross-entity links (`@implements REQ-xxx`, `@governed_by ADR-xxx`, `Fixes BUG-xxx`).

### 2. Automated CI/CD Sync on PR Merge
Add the GitHub Action in [`.github/workflows/codegraph-sync.yml`](file:///Users/ashwin/Documents/Projects/GraphHack/.github/workflows/codegraph-sync.yml) to continuously sync your graph whenever a PR merges to `main`.

### 3. Deploy as a Production Microservice
Start the server in HTTP/SSE transport mode:

```bash
MCP_TRANSPORT=streamable-http \
MCP_HTTP_HOST=0.0.0.0 \
MCP_HTTP_PORT=8000 \
FALKORDB_HOST=falkordb-cluster.prod.internal \
python -m codegraph serve
```

In customer environments, clients simply point their MCP config to the URL:

```json
{
  "mcpServers": {
    "codegraph": {
      "url": "https://codegraph.company.com/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_TOKEN}"
      }
    }
  }
}
```

---

### 4. Code Domain Owner Email Approval & Ingestion Workflow
When an AI agent or engineer fixes an incident via `record_bugfix()`, unapproved bug fixes do NOT immediately pollute the central knowledge graph:
1. **Domain Owner Lookup:** The affected file/function is resolved against [`.github/CODEOWNERS`](file:///Users/ashwin/Documents/Projects/GraphHack/.github/CODEOWNERS) (e.g. `demo_data/code/payment_service.py` $\to$ `payment-domain-owner@payflow.internal`).
2. **Email Dispatch:** A cryptographic approval token is generated and an actionable approval email is sent to the Code Domain Owner via standard library `smtplib`.
3. **Verified DB Ingestion:** The owner can approve via:
   - One-Click HTTP link: `http://localhost:8000/api/approve?ticket=BUG-342&token=<token>`
   - CLI command: `uv run python -m codegraph approve-bugfix --ticket BUG-342 --token <token>`
   - MCP tool: `approve_bugfix_via_email(ticket_id="BUG-342", approval_token="<token>")`
4. **Graph Activation:** Upon validation, the fix status is upgraded to `APPROVED`, `approved_by` is bound to the owner's email, and the relationship `(:Fix)-[:FIXES_FUNCTION {status: 'APPROVED'}]->(:Function)` is permanently activated in FalkorDB.

### 5. PRD Agent Updates & PRD Owner Email Approval Workflow
When an AI agent (e.g. Product Advisor or backlog generator) proposes new features or acceptance scenarios via `update_prd_features_and_scenarios()`, unapproved requirements do NOT inflate coverage metrics or alter active quality gates:
1. **PRD Owner Resolution:** The root `Project` node's `prd_owner` attribute is resolved (e.g. `product-lead@payflow.internal`).
2. **Staged Isolation:** The proposed requirement and scenarios are staged in FalkorDB with status `PENDING_APPROVAL`. Both `query_prd_coverage()` and `list_uncovered_requirements()` ignore staged nodes to preserve metric integrity.
3. **Email Dispatch:** A cryptographic approval token is generated and an actionable approval email containing feature specifications and scenario criteria is sent to the PRD Owner.
4. **Verified DB Ingestion:** The PRD Owner can approve via:
   - One-Click HTTP link: `http://localhost:8000/api/approve-prd?feature_id=REQ-011&token=<token>&approver=<email>`
   - CLI command: `uv run python -m codegraph approve-prd --feature-id REQ-011 --token <token> --approver product-lead@payflow.internal`
   - MCP tool: `approve_prd_update_via_email(feature_id="REQ-011", approval_token="<token>", approver_email="...")`
5. **Graph Activation:** Upon token validation, the requirement and scenario statuses are promoted to `APPROVED`, `approved_by` is recorded, and the relationships `(:Project)-[:SPECIFIES_REQUIREMENT]->(:FunctionalRequirement)` and `(:FunctionalRequirement)-[:HAS_SCENARIO]->(:Scenario)` are activated in the knowledge graph.

### 6. Ingesting Jira Board & Agile Sprints (5th Pillar)
Ingest Jira board data (Epics, Features, Stories) to connect agile project execution with the PRD, ADR, CodeBase, and Operations pillars:
```bash
uv run python -m codegraph ingest \
  --project-name "PayFlow" \
  --project-id "project:payflow" \
  --code ./demo_data/code \
  --prd ./demo_data/prd \
  --adr ./demo_data/adr \
  --jira ./demo_data/jira/jira_board_export.json
```
The ingestion parser automatically maps:
- `Project` ➔ `HAS_EPIC` ➔ `Epic`
- `Epic` ➔ `HAS_FEATURE` ➔ `AgileFeature`
- `AgileFeature` ➔ `HAS_STORY` ➔ `Story`
- Synthesizes `REALIZES_REQUIREMENT` to PRD and `IMPLEMENTS_CODE` to AST functions.

---

## 🧪 Running Automated Tests

Run the full 83-test pytest suite:

```bash
uv run pytest -v
# 83 passed in 0.71s
```

The modular test suite in [`tests/`](file:///Users/ashwin/Documents/Projects/GraphHack/tests/) provides comprehensive test coverage:
* `test_db_engine.py`: Graph database engine, CRUD, neighbor traversal, and fallback storage
* `test_parsers.py`: Multi-language code parser (Python AST, TypeScript, Go), document converter (HTML, JSON/Jira, Markdown, Plain Text), PRD & ADR parsers, runbooks
* `test_email_approval.py`: Code Domain Owner resolution (.github/CODEOWNERS), email dispatch, token verification, and DB ingestion
* `test_prd_agent_updates.py`: Agent PRD updates, staged status isolation, PRD Owner email dispatch, token verification, and DB ingestion
* `test_program_tools.py`: Program Manager persona tools, Jira ingestion, velocity metrics, root-cause bottleneck diagnosis, lead time analysis, and 5-pillar traceability
* `test_project_owners.py`: Project dual-ownership model (`codebase_owner` & `prd_owner`), pipeline ingestion, and status CLI
* `test_product_tools.py`: PRD compliance metrics, plain-English scenario simulation, change timeline
* `test_developer_tools.py`: Incident diagnostics, safe-to-change checks, 4-pillar lineage, PR diff audits
* `test_shared_and_ingest.py`: Full-text search, N-hop neighborhood expansion, unified pipeline, approval workflow
* `test_mcp_server.py`: Async MCP 2.x server initialization, 25 tools registry, persona prompts (`product_advisor`, `developer_assistant`, `program_manager`)
* `test_cli.py`: Click CLI commands (`status`, `demo`, `seed`, `ingest`, `approve-bugfix`, `approve-prd`, `help`)

---

## 🏆 Hackathon Track Criteria Alignment

- **Multi-hop reasoning:** `simulate_scenario`, `trace_requirement_to_delivery_chain`, and `diagnose_delivery_bottlenecks` traverse chains: `PRD -> Epic -> Feature -> Story -> Function -> Decisions -> Issues`.
- **Graph queries as agent tools:** All 25 tools generate and execute OpenCypher queries against FalkorDB.
- **Tool selection through MCP:** Standardized MCP 2.x protocol allows seamless tool discovery and persona invocation by any agent client.
- **Actions based on graph shows:** Produces concrete safety verdicts (`SAFE` vs `UNSAFE`), RCAs with line numbers, blocker diagnoses, and PR merge gating (`REQUEST_CHANGES` vs `APPROVE`).
- **Explainable results:** Every tool response includes `cypher_query` and `traversal_path` demonstrating exact data lineage.

---

## 🏛️ Project Architecture Decision Records (ADRs)

Foundational architectural decisions for every CodeGraph component are documented under [`docs/adr/`](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/README.md):

* [**ADR-001:** FalkorDB Graph Engine and Offline Fallback Architecture](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/001-falkordb-graph-engine-and-offline-fallback.md)
* [**ADR-002:** Four-Pillar Connected Knowledge Graph Data Model](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/002-four-pillar-graph-data-model.md)
* [**ADR-003:** Model Context Protocol (MCP) as Universal Agent Interface](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/003-mcp-server-as-universal-agent-interface.md)
* [**ADR-004:** Persona-Driven Multi-Agent Architecture](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/004-persona-driven-multi-agent-system.md)
* [**ADR-005:** Deterministic AST and Markdown Ingestion Pipeline](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/005-deterministic-ast-and-document-ingestion.md)
* [**ADR-006:** Human-in-the-Loop Quality Approval Gate for Operations](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/006-human-in-the-loop-approval-workflow.md)
* [**ADR-007:** Dual-Transport Deployment Strategy (Stdio vs Streamable-HTTP)](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/007-dual-transport-deployment-strategy.md)
* [**ADR-008:** Comprehensive Verification & Test Strategy](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/008-comprehensive-verification-and-test-strategy.md)
* [**ADR-009:** Unified Production Ingestion Pipeline & Auto-Linker](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/009-unified-production-ingestion-pipeline.md)
* [**ADR-010:** Multi-Format Enterprise Document & Polyglot Ingestion Adapter](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/010-multi-format-enterprise-document-and-polyglot-ingestion.md)
* [**ADR-011:** Code Domain Owner Email Approval & Ingestion Workflow](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/011-domain-owner-email-approval-and-ingestion-flow.md)
* [**ADR-012:** Project Entity Dual-Ownership Model (Codebase & PRD Owner)](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/012-project-entity-dual-ownership-model.md)
* [**ADR-013:** PRD Agent Updates and PRD Owner Email Approval Workflow](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/013-prd-agent-updates-and-owner-approval-workflow.md)
* [**ADR-014:** Program Manager Persona and Agile Execution Flow (5th Pillar)](file:///Users/ashwin/Documents/Projects/GraphHack/docs/adr/014-program-manager-persona-and-agile-execution-flow.md)






