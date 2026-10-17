"""
CodeGraph Seeding Script.
Orchestrates ingestion of PRDs, ADRs, Code, Runbooks, and Change History.
Constructs multi-hop relationships across Code, Requirements, Decisions, and Quality Records.
"""

import os
from pathlib import Path
from codegraph.db import db
from codegraph.schema import Relationships
from codegraph.ingest.code_parser import CodebaseParser
from codegraph.ingest.prd_parser import PRDParser
from codegraph.ingest.adr_parser import ADRParser
from codegraph.ingest.change_tracker import ChangeTracker


def seed_all():
    print("🚀 Initializing CodeGraph Seeding...")
    db.clear()

    base_dir = Path(__file__).resolve().parent
    demo_dir = base_dir / "demo_data"

    # 1. Ingest PRD
    prd_path = demo_dir / "prd" / "payment-gateway-prd.md"
    print(f"📄 Ingesting PRD from {prd_path.name}...")
    prd_parser = PRDParser()
    prd_res = prd_parser.parse_file(str(prd_path))
    print(f"   ✓ Ingested PRD: {prd_res.get('title')} ({prd_res.get('requirements_ingested')} reqs, {prd_res.get('scenarios_ingested')} scenarios)")

    # 2. Ingest ADRs
    adr_dir = demo_dir / "adr"
    print("🏛️ Ingesting Architectural Decision Records (ADRs)...")
    adr_parser = ADRParser()
    for adr_file in sorted(adr_dir.glob("*.md")):
        adr_res = adr_parser.parse_file(str(adr_file))
        print(f"   ✓ Ingested ADR: {adr_res.get('title')}")

    # 3. Ingest Codebase AST
    code_dir = demo_dir / "code"
    print("💻 Ingesting Codebase AST (Files, Classes, Functions, Calls)...")
    code_parser = CodebaseParser()
    code_res = code_parser.parse_directory(str(code_dir))
    print(f"   ✓ Ingested {len(code_res)} code files with full AST")

    # 4. Ingest Runbooks and BugFixes
    runbook_path = demo_dir / "runbooks" / "payment-failure-debug.md"
    print(f"📋 Ingesting Runbooks & Incidents from {runbook_path.name}...")
    tracker = ChangeTracker()
    rb_res = tracker.parse_runbook(str(runbook_path))
    print(f"   ✓ Ingested Runbook with {rb_res.get('bugs_extracted')} historical incidents")

    # Helper: Find function node ID by name
    def get_func_id(fn_name: str) -> str:
        for nid, node in db.memory_graph.nodes.items():
            if node["label"] == "Function" and node["properties"].get("name") == fn_name:
                return nid
        return ""

    # 5. Link Requirements -> Code Functions (IMPLEMENTED_BY)
    print("🔗 Linking PRD Requirements to Implementation Code...")
    req_func_mappings = {
        "REQ-001": ["authorize_payment"],
        "REQ-002": ["validate_card"],
        "REQ-003": ["assess_risk"],
        "REQ-005": ["authorize_payment"],
        "REQ-006": ["send_webhook"],
        "REQ-007": ["execute_refund", "validate_refund_eligibility"],
        "REQ-009": ["send_webhook"],
        "REQ-010": ["retry_with_backoff"]
        # REQ-004 (Multi-currency DCC) and REQ-008 (Partial refunds) are intentionally UNIMPLEMENTED
    }

    for req_id, fn_names in req_func_mappings.items():
        for fn_name in fn_names:
            fn_id = get_func_id(fn_name)
            if fn_id:
                db.create_edge(req_id, Relationships.IMPLEMENTED_BY, fn_id, {"status": "ACTIVE"})

    # 6. Link ADR Decisions -> Code Functions (AFFECTS) & Requirements (RELATES_TO)
    print("🔗 Linking ADR Constraints to Affected Code Functions...")
    adr_func_mappings = {
        "dec:ADR-001:core": ["retry_with_backoff", "assess_risk"],
        "dec:ADR-002:core": ["execute_refund", "queue_refund_job"]
    }
    for dec_id, fn_names in adr_func_mappings.items():
        for fn_name in fn_names:
            fn_id = get_func_id(fn_name)
            if fn_id:
                db.create_edge(dec_id, Relationships.AFFECTS, fn_id, {"enforced": True})

    db.create_edge("ADR-001", Relationships.RELATES_TO, "REQ-003")
    db.create_edge("ADR-001", Relationships.RELATES_TO, "REQ-010")
    db.create_edge("ADR-002", Relationships.RELATES_TO, "REQ-007")

    # 7. Record Historical Commits & Link to Functions + BugFixes
    print("📜 Recording Historical Change Records and Quality Lineage...")
    commits = [
        {
            "hash": "a1b2c3d4e5",
            "author": "sarah.dev@payflow.internal",
            "date": "2025-10-15",
            "message": "feat(core): implement initial card validation & Luhn algorithm per PRD REQ-002",
            "reason": "PRD_REQUIREMENT",
            "reason_id": "REQ-002",
            "file": "payment_service.py",
            "func": "validate_card"
        },
        {
            "hash": "e4f5a6b7c8",
            "author": "alex.arch@payflow.internal",
            "date": "2025-11-22",
            "message": "refactor(fraud): enforce ADR-001 mandatory 3-retry ceiling with exponential backoff",
            "reason": "ADR_ENFORCEMENT",
            "reason_id": "ADR-001",
            "file": "fraud_detector.py",
            "func": "retry_with_backoff"
        },
        {
            "hash": "f1e2d3c4b5",
            "author": "marcus.sec@payflow.internal",
            "date": "2026-01-05",
            "message": "fix(fraud): restore MAX_RETRIES=3 to resolve BUG-112 network drop false declines",
            "reason": "BUG_FIX",
            "reason_id": "BUG-112",
            "file": "fraud_detector.py",
            "func": "retry_with_backoff"
        },
        {
            "hash": "b7c8d9e0f1",
            "author": "david.infra@payflow.internal",
            "date": "2026-02-18",
            "message": "fix(refund): set worker concurrency to 5 per ADR-002 to resolve BUG-342 REFUND_TIMEOUT",
            "reason": "BUG_FIX",
            "reason_id": "BUG-342",
            "file": "refund_processor.py",
            "func": "queue_refund_job"
        }
    ]

    for c in commits:
        tracker.record_commit(
            commit_hash=c["hash"],
            author=c["author"],
            date=c["date"],
            message=c["message"],
            reason=c["reason"],
            reason_id=c["reason_id"],
            file_path=c["file"],
            target_func_name=c["func"]
        )

    # Link BugFixes -> Code Functions and Change Records
    db.create_edge("BUG-342", Relationships.FIXED_IN, get_func_id("queue_refund_job"))
    db.create_edge("BUG-342", Relationships.FIXED_IN, get_func_id("execute_refund"))
    db.create_edge("BUG-342", Relationships.FIXED_BY, "commit:b7c8d9e")

    db.create_edge("BUG-112", Relationships.FIXED_IN, get_func_id("retry_with_backoff"))
    db.create_edge("BUG-112", Relationships.FIXED_BY, "commit:f1e2d3c")

    db.create_edge("BUG-298", Relationships.FIXED_IN, get_func_id("retry_with_backoff"))

    # Link Runbook procedures to Functions
    rf_func_id = get_func_id("execute_refund")
    rb_proc_342 = "proc:RB-PAY-001:BUG-342"
    if rf_func_id and rb_proc_342 in db.memory_graph.nodes:
        db.create_edge(rb_proc_342, Relationships.DOCUMENTS, rf_func_id)

    fraud_retry_id = get_func_id("retry_with_backoff")
    rb_proc_112 = "proc:RB-PAY-001:BUG-112"
    if fraud_retry_id and rb_proc_112 in db.memory_graph.nodes:
        db.create_edge(rb_proc_112, Relationships.DOCUMENTS, fraud_retry_id)

    db.flush()

    info = db.get_backend_info()
    print("\n✅ Knowledge Graph Successfully Seeded!")
    print(f"   Backend: {info['backend']}")
    print(f"   Nodes: {len(db.memory_graph.nodes)}")
    print(f"   Edges: {len(db.memory_graph.edges)}")


if __name__ == "__main__":
    seed_all()
