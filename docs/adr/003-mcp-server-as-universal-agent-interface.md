# ADR-003: Model Context Protocol (MCP) as Universal Agent Interface

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Interface & Integration Layer (`codegraph/mcp_server.py`)

---

## Context
Traditional AI hackathon prototypes build dedicated web user interfaces (e.g., Streamlit, Gradio, React). However, modern engineering and product teams do not want another isolated dashboard. Engineers work inside IDEs (Antigravity, Cursor, VS Code Copilot) and LLM desktop clients (Claude Desktop). 

To ensure CodeGraph can be readily adopted, easily demoed, and deployed directly into customer development environments, a standardized, client-agnostic protocol was necessary.

## Decision
1. **Adopt MCP (Model Context Protocol) 2.x as the Single Product Interface:**
   - Eliminate all bespoke frontend dashboard code. The MCP server **is** the interface.
   - Any compliant MCP client (Claude Desktop, Antigravity, Cursor, Copilot, CLI) connects directly.
2. **Standardized Tool Exposure:**
   - Expose all graph queries, simulations, safety audits, and ingestion routines as typed MCP tools via `mcp.server.mcpserver.MCPServer`.
   - Tool arguments and returns use strict Pydantic schemas.
3. **Universal Client Configuration:**
   - Standardize client registration across all platforms using a single declarative JSON block:
     ```json
     {
       "mcpServers": {
         "codegraph": {
           "command": "python",
           "args": ["-m", "codegraph", "serve"],
           "env": { "FALKORDB_HOST": "localhost", "FALKORDB_PORT": "6379" }
         }
       }
     }
     ```

## Consequences
- **Positive:**
  - Zero frontend code to maintain, debug, or deploy.
  - Native agent integration: tools appear automatically in agent function-calling registries.
  - Customers can deploy CodeGraph into their existing developer toolchains without workflow disruption.
- **Negative:**
  - Visual graph canvas rendering depends on external browser tools (e.g. FalkorDB Browser on `:3000`) rather than in-chat canvas rendering.
- **Invariants:**
  - Every tool registered in `mcp_server.py` MUST return an `ExplainableResult` containing structured payload, the underlying Cypher query, and the traversal explanation.
