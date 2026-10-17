# ADR-005: Deterministic AST and Markdown Document Ingestion Pipeline

- **Status:** ACCEPTED
- **Date:** 2026-10-17
- **Author:** CodeGraph Architecture Team
- **Component:** Ingestion Pipeline (`codegraph/ingest/`)

---

## Context
Ingesting software repositories into knowledge graphs is often done using brittle regular expressions or heavy external LLM-based chunking that is nondeterministic, slow, and expensive. Code extraction must reliably identify classes, functions, argument signatures, docstrings, and call hierarchies without introducing external parsing dependencies.

Similarly, PRD and ADR documents are written by humans in Markdown with standard conventions (headings, priority badges, consequence sections, error tables).

## Decision
1. **Python Standard Library `ast` for Code Parsing:**
   - Use Python's built-in `ast` module in [`code_parser.py`](file:///Users/ashwin/Documents/Projects/GraphHack/codegraph/ingest/code_parser.py).
   - Zero external binary dependencies (e.g., Tree-sitter binaries) required for Python ingestion.
   - Walk the AST tree to extract:
     - `FileNode`
     - `ClassNode` (with line ranges and docstring)
     - `FunctionNode` (with exact signatures and line ranges)
     - `CALLS` edges between caller and callee function nodes.
2. **Structured Regex Section Parsers for Markdown:**
   - Implement deterministic markdown chunking in `prd_parser.py`, `adr_parser.py`, and `change_tracker.py`.
   - Extract IDs, priorities, statuses, guardrails, decisions, and consequence blocks deterministically.
3. **Automated Cross-Entity Reconciliation:**
   - The seeder reconciles unresolved call targets (`func_call_target:callee_name`) against real discovered functions and binds requirements to functions.

## Consequences
- **Positive:**
  - 100% deterministic parsing: identical source code always produces the exact same graph representation.
  - Sub-second ingestion: entire demo codebase and docs parsed in <0.2 seconds.
  - Zero third-party compilation or platform-specific C-library compilation issues.
- **Negative:**
  - Non-Python codebases (e.g. Go, Rust, Java) will require additional parsers or Tree-sitter bindings in future extensions.
- **Invariants:**
  - Ingestion parsers MUST extract exact 1-indexed `line_start` and `line_end` positions for every parsed function.
