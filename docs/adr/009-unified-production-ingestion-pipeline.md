# ADR-009: Unified Production Ingestion Pipeline & Auto-Linker

**ADR ID:** `ADR-009`  
**Title:** Unified Production Ingestion Pipeline & Auto-Linker  
**Status:** `ACCEPTED`  
**Date:** `2026-10-18`  
**Author:** CodeGraph Architecture Working Group  

---

## Context
While the PayFlow sample dataset (`seed.py`) showcases baseline graph traversal capabilities, real-world enterprise adoption requires connecting arbitrary codebases, documentation folders, and git histories without writing bespoke code or hardcoding schema models.
In production:
1. Source code lives in git repositories (`./src`, `./lib`).
2. PRDs live in markdown directories (`./docs/prd/*.md`) or Jira exports.
3. Architecture Decision Records live in `./docs/adr/*.md`.
4. Incident postmortems live in `./docs/runbooks/*.md`.
5. Recent commits and rationale live in the local `.git` commit log.
6. A mechanism is required to automatically infer and establish cross-entity links without manual edge definition.

## Decision
We implement a zero-dependency, unified production orchestrator (`codegraph/ingest/pipeline.py`) exposed via CLI command (`codegraph ingest`) and CI/CD webhooks:
1. **Multi-Directory Ingestion:** Sequentially processes code, PRD markdown, ADR markdown, and runbook directories into typed graph nodes.
2. **Git Commit History Extractor:** Calls standard `git log` to extract recent commit hashes, authors, timestamps, and commit messages into `ChangeTimelineNode` entities.
3. **Automated Cross-Entity Synthesizer (Auto-Linker):**
   - Scans function and class docstrings for requirement tags (e.g. `Implements REQ-xxx`), ADR tags (e.g. `Governed by ADR-xxx`), and incident tags (e.g. `caused BUG-xxx`).
   - Automatically generates the corresponding graph relationships (`IMPLEMENTED_BY_FUNCTION`, `CONSTRAINS_FUNCTION`, `MANIFESTED_IN_FUNCTION`).
   - Analyzes commit messages to link `ChangeTimeline` entries to their motivating PRD, ADR, or BugFix nodes (`MOTIVATED_BY_PRD`, `MOTIVATED_BY_ADR`, `MOTIVATED_BY_FIX`).
4. **Environment-Only Configuration:** Transitioning from local fallback to enterprise cloud FalkorDB clusters requires zero code changes—only updating `FALKORDB_HOST`, `FALKORDB_PORT`, and `FALKORDB_PASSWORD`.

## Consequences

### Positive Impact
- **Turnkey Production Onboarding:** Any engineering team can point `codegraph ingest` at their repository to build an immediate connected knowledge graph.
- **CI/CD Automation:** Integrates seamlessly into GitHub Actions, GitLab CI, or Jenkins on every PR merge.
- **Eliminates Manual Edge Tagging:** Auto-Linker infers cross-entity relationships directly from standard engineering conventions (docstrings and conventional commit messages).

### Tradeoffs
- Codebase parsing currently uses standard library Python AST; non-Python codebases (TypeScript, Go, Java) require adding corresponding AST or Tree-Sitter parsers.

## Architectural Invariants
1. `ENV_DRIVEN_CREDENTIALS`: Production database endpoints must be supplied strictly via environment variables.
2. `FAIL_SAFE_AUTO_LINKING`: Missing docstring tags must never fail ingestion; untagged functions remain discoverable via full-text search.
3. `ZERO_CODE_DEPLOYMENT`: Moving from local storage to cloud clusters must never require code modifications.
