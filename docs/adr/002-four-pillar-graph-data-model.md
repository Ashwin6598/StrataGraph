# ADR-002: Four-Pillar Connected Knowledge Graph Data Model

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Knowledge Graph Schema & Domain Model (`codegraph/schema.py`)

---

## Context
Initial implementations treated Code, PRDs, and ADRs as loosely coupled metadata tables. This made it difficult to trace *why* a line of code was created, which specific guardrail was violated during an incident, and how an architectural decision was derived from customer requirements. 

A unified, structured domain model was required where:
- Code is demonstrably built from ADRs, which are built from PRDs.
- Operational incident fixes directly remediate the codebase and restore architectural invariants.
- All entities anchor to a single root project.
- Every modification preserves chronological timeline lineage ("what changed" and "why it changed").

## Decision
Adopt a **5-Pillar Connected Knowledge Graph** anchored by `Project` (which explicitly stores `codebase_owner` and `prd_owner` per ADR-012):

1. **CodeBase Chain:**
   `Project` ➔ `CodeInput` ➔ `LogicFlow` ➔ `Class` ➔ `Function` ➔ `CodeLogic` ➔ `CodeOutput`
2. **PRD Chain:**
   `Project` ➔ `PRDInput` ➔ `FunctionalRequirement` ➔ `Guardrail` ➔ `PRDOutput`
3. **ADR Chain:**
   `Project` ➔ `ADRRequirement` ➔ `Architecture` ➔ `Decision` ➔ `ADRResult`
4. **Operations Chain:**
   `Project` ➔ `Issue` ➔ `RCA` ➔ `Fix` ➔ `OpResult`
5. **Program Flow Chain (Agile / Jira Execution per ADR-014 & ADR-015):**
   `Project` ➔ `Epic` ➔ `AgileFeature` ➔ `Story` ➔ `Developer / AST Function`
6. **Timeline & Quality Lineage:**
   `ChangeTimeline` records both `what_changed` and `why_changed`, with explicit motivations linking to `FunctionalRequirement`, `Decision`, and `Fix`.

### Cross-Entity Interlinks:
- `(FunctionalRequirement)-[:DRIVES_ADR_REQUIREMENT]->(ADRRequirement)`
- `(Guardrail)-[:JUSTIFIES_DECISION]->(Decision)`
- `(Decision)-[:CONSTRAINS_FUNCTION]->(Function)`
- `(Decision)-[:ENFORCED_IN_CODE_LOGIC]->(CodeLogic)`
- `(FunctionalRequirement)-[:IMPLEMENTED_BY_FUNCTION]->(Function)`
- `(Guardrail)-[:VERIFIED_BY_LOGIC]->(CodeLogic)`
- `(Issue)-[:MANIFESTED_IN_FUNCTION]->(Function)`
- `(Issue)-[:VIOLATED_DECISION]->(Decision)`
- `(Fix)-[:FIXES_FUNCTION]->(Function)`
- `(Fix)-[:MODIFIES_CODE_LOGIC]->(CodeLogic)`
- `(AgileFeature | Story)-[:REALIZES_REQUIREMENT]->(FunctionalRequirement)`
- `(AgileFeature | Story)-[:GUIDED_BY_ARCHITECTURE]->(Architecture | Decision)`
- `(Story)-[:IMPLEMENTS_CODE]->(Function)`
- `(Story)-[:RESOLVES_ISSUE]->(Issue)`

## Consequences
- **Positive:**
  - True end-to-end traceability from customer business rules down to individual lines of AST logic and incident post-mortems.
  - Multi-hop reasoning can trace impact chains: PRD Requirement ➔ Architecture ➔ Code Function ➔ Incident RCA.
  - New developers immediately know *why* an invariant exists before attempting blind code overrides.
- **Negative:**
  - Requires richer data ingestion contracts compared to unstructured document dumping.
- **Invariants:**
  - Every `FunctionNode` MUST trace back to either a `FunctionalRequirementNode` or an `ADRRequirementNode`.
  - Every `FixNode` MUST link to the affected `FunctionNode` and modified `CodeLogicNode`.
