# ADR-006: Human-in-the-Loop Quality Approval Gate for Operations Mutations

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Operational Mutations (`codegraph/tools/ingest_tools.py`)

---

## Context
When developers or coding agents fix a production bug, the RCA and fix details must feed back into the knowledge graph to prevent future regressions. However, allowing agents or junior developers to mutate the active graph database unconditionally could index flawed RCAs, weaken architectural guardrails, or corrupt safety checks across the organization.

The user's requirements explicitly mandate: *"this feedback to the graph DB has to be done with an approval process"*.

## Decision
1. **Mandatory Approval Flag on Operational Feedback:**
   - In `record_bugfix`, mandate an explicit `approved_by_lead: bool = False` parameter.
2. **Two-Stage Mutation Lifecycle:**
   - **`PENDING_APPROVAL`:** When `approved_by_lead == False`:
     - The `IssueNode` and `FixNode` are written to the graph with status `PENDING_APPROVAL`.
     - The fix is recorded for auditing, but the affected `FunctionNode` is NOT marked as having an approved architectural update.
     - The tool explicitly returns a warning that lead review is required.
   - **`APPROVED`:** When `approved_by_lead == True`:
     - The relationship `(:Fix)-[:FIXES_FUNCTION {status: 'APPROVED'}]->(:Function)` is activated.
     - The incident is permanently indexed for automated PR diff reviews and safety audits.

## Consequences
- **Positive:**
  - Prevents hallucinated or flawed agent fixes from corrupting the organization-wide knowledge graph.
  - Satisfies enterprise compliance, SOC2 change-management, and quality auditing requirements.
- **Negative:**
  - Introduces a human verification step before an incident fix becomes an active constraint in the graph.
- **Invariants:**
  - Unapproved fixes (`approved_by_lead=False`) MUST NEVER modify or supersede an existing `DecisionNode` (ADR).
