# ADR-015: Cross-Team Capability Unlocking and Domain Synergy Architecture

**ADR ID:** `ADR-015`  
**Title:** Cross-Team Capability Unlocking and Domain Synergy Architecture  
**Status:** `ACCEPTED`  
**Date:** `2026-10-18`  
**Author:** CodeGraph Architecture Working Group  
**Component:** `codegraph/tools/program_tools.py`, `codegraph/mcp_server.py`, `prompts/program-persona.md`

---

## Context

In multi-service engineering organizations, software engineering teams typically operate in service silos:
1. **Domain Tunnel Vision:** A feature team (e.g., Checkout, Fraud, or Refunds) only views the repository and tickets directly assigned to their immediate service, unaware of analogous problems solved in adjacent team domains.
2. **Reinventing the Wheel:** Teams duplicate complex engineering effort—such as writing custom exponential backoff loops, building proprietary Redis idempotency locks, or implementing webhook dispatchers—even when production-hardened implementations already exist within the company.
3. **Cross-Domain Blocker Inertia:** When a ticket is blocked on external requirements (e.g. accounting rules, interchange fee schedules, or partner API specs), engineers stall waiting for external committee approvals, unaware that another team has already modeled the exact domain logic.

Technical Program Managers (TPMs) possess a unique architectural vantage point: they oversee initiatives across all Epics, Features, Services, and Engineering teams. By grounding the Program Manager persona in the connected knowledge graph, the agent can unlock cross-team capabilities to accelerate delivery.

---

## Decision

We introduce **Cross-Team Capability Unlocking** into the Program Manager Persona and implement the `unlock_cross_team_capabilities` tool in `codegraph/tools/program_tools.py`:

1. **Cross-Domain Graph Traversal:**
   The tool performs a unified multi-hop traversal from the root `Project`:
   $$\text{Project} \xrightarrow{\text{HAS\_EPIC}} \text{Epic} \xrightarrow{\text{HAS\_FEATURE}} \text{AgileFeature} \xrightarrow{\text{HAS\_STORY}} \text{Story} \xrightarrow{\text{IMPLEMENTS\_CODE}} \text{Function} \xrightarrow{\text{GUIDED\_BY}} \text{Decision}$$
   It aggregates features and stories into domain service clusters (`payment_service`, `fraud_detector`, `refund_processor`, `fx_service`, `notification_service`), computing:
   - Lead engineers and story point allocations per domain.
   - Verified code capabilities (AST function signatures and logic types: `RETRY_LOOP`, `QUEUE_CONCURRENCY`, `IDEMPOTENCY`, `VALIDATION`).
   - Governing architectural standards (`ADR-001`, `ADR-002`).

2. **Cross-Team Capability Catalog:**
   Maintains a knowledge catalog of production-verified, reusable architectural capabilities:
   - **Resilient Network Retries (`ADR-001` / `fraud_detector`):** 3-retry ceiling with exponential backoff resilient against network jitter.
   - **Decoupled Queue Worker Concurrency (`ADR-002` / `refund_processor`):** Concurrency-capped consumers preventing gateway starvation and HTTP 429 rate limits.
   - **Distributed Idempotency Locking (`REQ-009` / `payment_service`):** Redis-backed locking preventing duplicate financial mutations.
   - **Zero-Fee Pre-Flight Card Validation (`REQ-002` / `payment_service`):** Local checksums and expiry verification before hitting external payment rails.
   - **Asynchronous Webhook Event Dispatching (`REQ-006` / `notification_service`):** Signed asynchronous merchant notifications.

3. **Concrete Acceleration & Unblocking Recommendations:**
   Automatically maps stalled, unassigned, or blocked backlog items to ready-made cross-team solutions:
   - *Example 1 (Forex Integration):* Identifies that `fx_service` (`PAY-306`) in backlog can reuse `fraud_detector.retry_with_backoff` (`ADR-001`), saving ~5-8 story points of boilerplate.
   - *Example 2 (Cross-Domain Blocker Resolution):* Identifies that Sarah Jenkins (`PAY-307` partial refund interchange fee clawback) can be unblocked by connecting with Alice Chen (`payment_service`), whose checkout engine already computes merchant fee schedule breakdowns.

4. **MCP Interface & Persona Prompt Integration:**
   - Tool registered on the MCP server as `unlock_cross_team_capabilities`.
   - Program Manager Persona updated to proactively recommend cross-team pattern reuse and engineer-to-engineer pairing.

---

## Architecture Flow

```mermaid
graph TD
    TPM["Technical Program Manager<br/>(Program Advisor Agent)"]
    
    subgraph "Cross-Team Knowledge Graph Discovery"
        Proj["Project Anchor"] --> Svc1["Domain: payment_service<br/>(Alice Chen, Bob Martinez)"]
        Proj --> Svc2["Domain: fraud_detector<br/>(Bob Martinez)"]
        Proj --> Svc3["Domain: refund_processor<br/>(David Kim, Sarah Jenkins)"]
        Proj --> Svc4["Domain: fx_service<br/>(Unassigned Backlog)"]
    end
    
    subgraph "Reusable Production Capabilities"
        Cap1["Resilient 3-Retry Pipeline<br/>(ADR-001)"]
        Cap2["Distributed Idempotency Locks<br/>(REQ-009)"]
        Cap3["Fee Breakdown Engine<br/>(PAY-FEAT-201)"]
    end
    
    Svc2 --> Cap1
    Svc1 --> Cap2
    Svc1 --> Cap3
    
    TPM -->|unlock_cross_team_capabilities| Proj
    Cap1 -.->|Accelerates Integration (saves ~5-8 pts)| Svc4
    Cap3 -.->|Unblocks Interchange Clawback| Svc3
    Cap2 -.->|Guarantees Zero Double Payouts| Svc3
```

---

## Consequences

### Positive Impact
- **Eliminates Code Duplication:** Reuses proven, hardened infrastructure and integration patterns across microservice boundaries.
- **Dramatically Reduces Lead Time:** Features in backlog (e.g. DCC forex) can ship in days instead of weeks by adopting pre-existing client wrappers.
- **Breaks Down Organizational Silos:** Connects engineers across team boundaries based on grounded capability needs rather than guessing in all-hands meetings.

### Tradeoffs
- Cross-team capability reuse requires maintaining clean module boundaries and shared libraries or microservice contracts.

---

## Architectural Invariants
1. `CROSS_TEAM_GROUNDING`: All capability recommendations must cite the exact owning domain, implementing function, and governing ADR.
2. `DELIVERY_FIRST`: Unlocking suggestions must prioritize active blockers and high-point backlog items.
3. `CODE_FREE_TPM_EXPLANATION`: Explanations must be phrased in terms of story points saved, lead time reduction, and team pairing (no raw AST code snippets).
