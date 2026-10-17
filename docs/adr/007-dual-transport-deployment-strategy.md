# ADR-007: Dual-Transport Deployment Strategy (Stdio Local vs Streamable-HTTP Production)

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Deployment & Transport Layer (`codegraph/config.py`, `codegraph/mcp_server.py`)

---

## Context
CodeGraph must be trivial to run and demonstrate on a local developer laptop during the hackathon, while also being capable of immediate enterprise cloud deployment without code refactoring.

- **Local Development:** Developers want zero-process management: launching Claude Desktop or Antigravity should automatically start the MCP server via standard input/output (`stdio`) and shut it down when finished.
- **Enterprise Production:** Organizations need a centralized, multi-tenant microservice accessible over HTTPS/SSE with authentication tokens and webhooks.

## Decision
1. **Unified Dual-Transport Server:**
   - Implement native transport switching in `codegraph/mcp_server.py` driven by the `MCP_TRANSPORT` environment variable (`stdio`, `streamable-http`, or `sse`).
2. **Zero-Refactor Production Upgrade:**
   - The exact same Python codebase runs in both modes:
     - **Local Hackathon Mode:**
       ```bash
       MCP_TRANSPORT=stdio python -m codegraph serve
       ```
     - **Production Cloud Microservice Mode:**
       ```bash
       MCP_TRANSPORT=streamable-http MCP_HTTP_HOST=0.0.0.0 MCP_HTTP_PORT=8000 python -m codegraph serve
       ```
3. **Containerization:**
   - Package the service via `docker-compose.yml` linking to FalkorDB on internal Docker networks.

## Consequences
- **Positive:**
  - Zero code differences between local testing and production deployment.
  - Local developers enjoy instant `stdio` process lifecycle management.
  - Enterprise platforms can deploy CodeGraph behind Kubernetes ingresses or API gateways.
- **Negative:**
  - Production deployments require network security (TLS termination and bearer token validation) at the ingress level.
- **Invariants:**
  - The tool execution logic and graph access layer MUST be 100% agnostic to whether requests arrive over `stdio` or HTTP JSON-RPC streams.
