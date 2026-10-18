# ADR-011: Code Domain Owner Email Approval and Ingestion Workflow

**ADR ID:** `ADR-011`  
**Title:** Code Domain Owner Email Approval and Ingestion Workflow  
**Status:** `ACCEPTED`  
**Date:** `2026-10-18`  
**Author:** CodeGraph Architecture Working Group  
**Component:** `codegraph/approval_service.py`, `codegraph/tools/ingest_tools.py`, `codegraph/mcp_server.py`

---

## Context
When AI agents or automated SRE pipelines resolve a production incident or generate a Root Cause Analysis (RCA), directly mutating the active enterprise knowledge graph without domain authority introduces critical risks:
1. **Hallucination or Misdiagnosis:** An erroneous agent RCA could poison the knowledge base, causing future safety checks to enforce flawed constraints.
2. **Domain Boundaries:** Modern software organizations partition microservices among dedicated domain teams (e.g., Payment Core vs. Fraud & Risk vs. Settlements). A change affecting `payment_service.py` must not be approved by an unrelated team.
3. **Auditability & Compliance:** Enterprise SOC2 change management requires a provable audit trail establishing that the authorized domain owner signed off on the operational fix before it became an active architectural invariant.

The requirement mandates: *The approval will go to the Code Domain Owner via an email; once the email is approved, it should be ingested into the DB.*

## Decision

We implement a zero-dependency domain resolution, email dispatch, and token-verified ingestion workflow:

1. **Standard `CODEOWNERS` Domain Resolution (`codegraph/approval_service.py`):**
   - Automatically parses `.github/CODEOWNERS`, `CODEOWNERS`, or `docs/CODEOWNERS` to resolve domain owners for affected functions and source files.
   - Falls back to existing graph `FunctionNode.domain_owner` or the environment-configured `CODE_DOMAIN_OWNER`.

2. **Cryptographic Approval Token & Email Notification:**
   - When `record_bugfix` is called without prior lead approval (`approved_by_lead=False`), a cryptographically secure 16-byte approval token (`secrets.token_hex(16)`) is generated.
   - The fix is staged in the graph with status `PENDING_APPROVAL`, storing `approval_token` and `domain_owner_email`.
   - An email is formatted and dispatched to the Code Domain Owner via standard library `smtplib` and `email.message.EmailMessage` (with zero external email vendor dependencies).
   - In local and test environments, dispatched emails are captured in an in-memory audit outbox (`SENT_APPROVAL_EMAILS`) and written to `.codegraph_email_outbox.json` for deterministic offline verification.

3. **Multi-Channel Approval Actions:**
   The email provides the Code Domain Owner with three frictionless approval options:
   - **One-Click URL:** `http://<host>:<port>/api/approve?ticket=<id>&token=<token>&approver=<email>`
   - **CLI Command:** `uv run python -m codegraph approve-bugfix --ticket <id> --token <token> --approver <email>`
   - **MCP Agent Tool:** `approve_bugfix_via_email(ticket_id="<id>", approval_token="<token>")`

4. **Token-Verified Database Ingestion:**
   When approval is received via `approve_bugfix_and_ingest`:
   - Validates that the provided token matches the stored `approval_token` on `FixNode`.
   - Upgrades `approval_status` from `PENDING_APPROVAL` to `APPROVED`.
   - Records `approved_by` as the Code Domain Owner's email.
   - Activates the `(:Fix)-[:FIXES_FUNCTION {status: 'APPROVED'}]->(:Function)` graph edge in FalkorDB.
   - Persists the mutation and flushes to the backend database.

## Consequences

### Positive Impact
- **Prevents Unverified Graph Mutations:** Hallucinated or speculative agent fixes cannot enter the knowledge graph without the domain owner's signoff.
- **Enterprise Alignment:** Natively supports git `CODEOWNERS` conventions and multi-tenant engineering hierarchies.
- **Auditable & SOC2 Ready:** Stored `approved_by` and token timestamps prove who authorized each operational change.
- **Offline & Local Resilience:** Full functionality operates with zero external SMTP dependencies in local development and CI/CD testing.

### Tradeoffs
- Fixes remain staged in `PENDING_APPROVAL` until the human domain owner clicks or confirms the approval action.

## Architectural Invariants
1. `UNAPPROVED_FIX_INERT`: A fix with status `PENDING_APPROVAL` must never trigger blocking regression verdicts in `review_pr_diff()`.
2. `CRYPTOGRAPHIC_TOKEN_MATCH`: Status promotion to `APPROVED` strictly requires an exact match with the staged `approval_token`.
3. `RE_APPROVAL_IDEMPOTENCY`: Re-approving an already active fix must return `ALREADY_APPROVED` without duplicating edges.
