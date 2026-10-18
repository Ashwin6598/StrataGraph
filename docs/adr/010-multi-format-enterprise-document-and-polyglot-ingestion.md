# ADR-010: Multi-Format Enterprise Document & Polyglot Ingestion Adapter

**ADR ID:** `ADR-010`  
**Title:** Multi-Format Enterprise Document & Polyglot Ingestion Adapter  
**Status:** `ACCEPTED`  
**Date:** `2026-10-18`  
**Author:** CodeGraph Architecture Working Group  
**Component:** `codegraph/ingest/document_converter.py`, `codegraph/ingest/code_parser.py`

---

## Context
In real enterprise environments, product specifications, architectural records, and incident runbooks rarely exist exclusively as clean GitHub Markdown files. Teams manage their institutional knowledge across disparate platforms:
1. **Confluence Wikis:** Exported as rich HTML pages (`.html`, `.htm`).
2. **Jira Issue Trackers & OpenAPI/Swagger:** Exported as nested JSON structures (`.json`).
3. **Legacy Business Documents:** Stored as Microsoft Word documents (`.docx`) or PDFs (`.pdf`).
4. **Engineering Notes:** Stored as plain text notes (`.txt`) or native Markdown (`.md`, `.markdown`).
5. **Polyglot Codebases:** Modern microservices are written in diverse programming languages (Python, TypeScript, JavaScript, Go, Java, Kotlin, Rust).

Requiring engineering teams to manually re-author their documentation into Markdown or restricting code analysis to a single language creates significant onboarding friction.

## Decision

We implement a zero-dependency normalization pipeline that standardizes all enterprise inputs into typed knowledge graph entities while strictly preserving verbatim source text:

1. **Universal Document Converter (`codegraph/ingest/document_converter.py`):**
   - **Markdown (`.md`, `.markdown`) & Plain Text (`.txt`):** Ingested natively with UTF-8 encoding.
   - **HTML / Confluence (`.html`, `.htm`):** Normalized via Python's standard library `html.parser.HTMLParser` into structured markdown headings, lists, bold tags, and code blocks without third-party HTML scrapers.
   - **Jira JSON (`.json`):** Mapped into PRD Markdown structures (`REQ-xxx` headers, priority, status badges, descriptions, and acceptance criteria/scenarios).
   - **PDF (`.pdf`):** Extracted via system `pdftotext` or `pypdf` fallback.
   - **Word (`.docx`):** Extracted via platform tools (macOS `/usr/bin/textutil`, `pandoc`) or `python-docx`.

2. **Polyglot Code Parser (`codegraph/ingest/code_parser.py`):**
   - **Python:** Parsed via standard library `ast.walk` for 100% AST call-graph fidelity.
   - **TypeScript / JavaScript / Go / Java / Kotlin / Rust:** Parsed via an efficient zero-dependency universal lexer extracting classes, structs, function signatures, exported arrow functions, and docstrings/comments (`@implements`, `@governed_by`).

3. **Zero Data Loss Guarantee:**
   - Graph nodes store normalized properties for Cypher indexing (`id`, `title`, `priority`, `signature`), but also retain the verbatim unedited original content in `raw_content` (`PRDNode`, `ADRNode`) and `source_code` (`FunctionNode`).

## Consequences

### Positive Impact
- **Drop-in Enterprise Ingestion:** Teams can point `codegraph ingest` directly at raw Confluence HTML exports, Jira JSON dumps, or Word documents.
- **Zero Binary Bloat:** Core conversions (HTML, JSON, Text, Markdown, Python, TypeScript, Go) require zero external C-bindings or heavy pip dependencies.
- **Auditability:** Retaining `raw_content` and `source_code` allows agents and humans to inspect the exact original text alongside structured graph queries.

### Tradeoffs
- PDF and DOCX extraction fallback gracefully when platform utilities (`pdftotext`, `textutil`) or optional Python libraries are absent.

## Architectural Invariants
1. `FORMAT_AGNOSTIC_STORAGE`: Regardless of original file format (`.html`, `.json`, `.docx`, `.md`), all ingested requirements and decisions must conform to the canonical `PRDNode` and `ADRNode` schema in FalkorDB.
2. `VERBATIM_FIDELITY`: The ingestion pipeline must never discard or truncate original document content; `raw_content` must preserve full source fidelity.
