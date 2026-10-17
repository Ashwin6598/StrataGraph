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
│  └───────────────────────┴───────────────────────────────┘  │
│  ┌───────────────────────┬───────────────────────────────┐  │
│  │   Shared Search       │       Ingestion & Mutations   │  │
│  │  • search_graph       │      • ingest_code / prd / adr│  │
│  │  • get_related_nodes  │      • record_bugfix (Approval│  │
│  └───────────────────────┴───────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ OpenCypher
┌──────────────────────────────▼──────────────────────────────┐
│                    FalkorDB / Graph Store                   │
│                                                             │
│                      [ Root: Project ]                      │
│        ┌───────────────┬───────────────┬──────────────┐     │
│        ▼               ▼               ▼              ▼     │
│     [ PRD ]         [ ADR ]       [ CodeBase ]   [ Ops ]    │
│        │               │               │              │     │
│      Input        Requirement        Input          Issues  │
│        │               │               │              │     │
│  Functional Req   Architecture    Logic Flow         RCA    │
│        │               │               │              │     │
│   Guardrails       Decisions        Classes           Fix   │
│        │               │               │              │     │
│     Output          Result         Functions        Result  │
│        ▲               ▲               │              ▲     │
│        │               │          Code Logic          │     │
│        │               │               │              │     │
│        │               │            Output            │     │
│        └───────────────┴───────────────┴──────────────┘     │
│                                                             │
│   [ Timeline & History: ChangeTimeline (What & Why) ]      │
└─────────────────────────────────────────────────────────────┘
```

### 🔗 The 4-Pillar Connected Data Model

All entities stem from **`Project`** and are interconnected across their lifecycle:

1. **CodeBase Chain:** `Project` ➔ `CodeInput` ➔ `LogicFlow` ➔ `Class` ➔ `Function` ➔ `CodeLogic` ➔ `CodeOutput`
2. **PRD Chain:** `Project` ➔ `PRDInput` ➔ `FunctionalRequirement` ➔ `Guardrail` ➔ `PRDOutput`
3. **ADR Chain:** `Project` ➔ `ADRRequirement` ➔ `Architecture` ➔ `Decision` ➔ `ADRResult`
4. **Operations Chain:** `Project` ➔ `Issue` ➔ `RCA` ➔ `Fix` ➔ `OpResult`
5. **Timeline & History:** `ChangeTimeline` records **WHAT** changed and **WHY** it changed, linked to `FunctionalRequirement`, `Decision`, and `Fix`.

#### Cross-Entity Interlinks:
* **Code is built from ADR:** `Decision` ➔ `CONSTRAINS_FUNCTION` / `ENFORCED_IN_CODE_LOGIC` ➔ `Function` / `CodeLogic`
* **ADR is built from PRD:** `FunctionalRequirement` ➔ `DRIVES_ADR_REQUIREMENT` ➔ `ADRRequirement`, `Guardrail` ➔ `JUSTIFIES_DECISION` ➔ `Decision`
* **Code implements PRD:** `FunctionalRequirement` ➔ `IMPLEMENTED_BY_FUNCTION` ➔ `Function`, `Guardrail` ➔ `VERIFIED_BY_LOGIC` ➔ `CodeLogic`
* **Operations fixes the CodeBase:** `Issue` ➔ `MANIFESTED_IN_FUNCTION`, `Issue` ➔ `VIOLATED_DECISION`, `Fix` ➔ `MODIFIES_CODE_LOGIC` / `FIXES_FUNCTION`

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

## 🎭 Two Personas, One Connected Graph

| Persona | System Prompt | Communication Style | Primary Tools |
|---------|---------------|---------------------|---------------|
| **Product Manager** | `prompts/product-persona.md` | Plain English, business terms, completion %, zero code | `query_prd_coverage`, `simulate_scenario`, `get_change_history`, `list_uncovered_requirements` |
| **Developer / SRE** | `prompts/developer-persona.md` | Technical, file paths, line numbers, ADR constraints | `debug_issue`, `check_safe_to_change`, `get_function_lineage`, `review_pr_diff`, `cross_org_bug_check` |

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

---

## 🚢 Production Deployment

Moving from local hackathon testing to enterprise cloud production requires **zero code changes**:

```bash
# 1. Start as a production HTTP/SSE microservice
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

## 🧪 Running Automated Tests

Run the full pytest suite:

```bash
pytest -v
# 13 passed in 0.54s
```

---

## 🏆 Hackathon Track Criteria Alignment

- **Multi-hop reasoning:** `simulate_scenario` and `get_related_entities` traverse chains: `Scenario -> Requirement -> Function -> Calls -> Decisions`.
- **Graph queries as agent tools:** All 15 tools generate and execute OpenCypher queries against FalkorDB.
- **Tool selection through MCP:** Standardized MCP 2.x protocol allows seamless tool discovery and invocation by any agent client.
- **Actions based on graph shows:** Produces concrete safety verdicts (`SAFE` vs `UNSAFE`), RCAs with line numbers, and PR merge gating (`REQUEST_CHANGES` vs `APPROVE`).
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

