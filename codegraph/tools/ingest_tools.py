"""
Ingestion MCP Tools for CodeGraph.
Allows AI Agents and CI/CD pipelines to dynamically mutate and update the knowledge graph.
Includes an explicit human approval workflow for recording new BugFixes and Root Cause Analyses.
"""

from typing import Dict, Any, Optional
from ..db import db
from ..schema import BugFixNode, Relationships, ExplainableResult
from ..ingest.code_parser import CodebaseParser
from ..ingest.prd_parser import PRDParser
from ..ingest.adr_parser import ADRParser
from ..ingest.change_tracker import ChangeTracker


def ingest_codebase(directory_path: str) -> Dict[str, Any]:
    """
    Ingests source code files from a directory into AST nodes (Files, Classes, Functions, Calls).
    """
    parser = CodebaseParser()
    results = parser.parse_directory(directory_path)
    return {
        "status": "SUCCESS",
        "files_processed": len(results),
        "details": results
    }


def ingest_prd(file_path: str) -> Dict[str, Any]:
    """
    Ingests a Product Requirements Document (PRD) markdown file into Requirements and Scenarios.
    """
    parser = PRDParser()
    return parser.parse_file(file_path)


def ingest_adr(file_path: str) -> Dict[str, Any]:
    """
    Ingests an Architecture Decision Record (ADR) markdown file into Decisions and Constraints.
    """
    parser = ADRParser()
    return parser.parse_file(file_path)


def ingest_runbook(file_path: str) -> Dict[str, Any]:
    """
    Ingests an incident runbook markdown file into Runbooks and historical BugFix nodes.
    """
    tracker = ChangeTracker()
    return tracker.parse_runbook(file_path)


def record_bugfix(
    ticket_id: str,
    symptom: str,
    rca: str,
    fix_summary: str,
    affected_function_name: str,
    approved_by_lead: bool = False,
    date: str = "2026-10-17"
) -> Dict[str, Any]:
    """
    Records a resolved production bug, RCA, and verified fix into the knowledge graph.
    Enforces the mandatory approval workflow: unapproved bug fixes are flagged as PROPOSED and do not mutate active constraints.
    """
    status = "APPROVED" if approved_by_lead else "PENDING_APPROVAL"

    bug_node = BugFixNode(
        id=ticket_id,
        ticket=ticket_id,
        symptom=symptom,
        description=f"Incident {ticket_id}: {symptom}",
        rca=rca,
        fix_summary=fix_summary,
        approved=approved_by_lead,
        date=date
    )
    db.create_node(ticket_id, "BugFix", bug_node.model_dump())

    # Find affected function
    target_fn_id = None
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Function" and node["properties"].get("name") == affected_function_name:
            target_fn_id = nid
            break

    if target_fn_id:
        db.create_edge(ticket_id, Relationships.FIXED_IN, target_fn_id, {"approval_status": status})

    db.flush()

    cypher = f"""
    MERGE (b:BugFix {{id: '{ticket_id}'}})
    SET b.symptom = '{symptom}', b.rca = '{rca}', b.approved = {str(approved_by_lead).lower()}
    WITH b
    MATCH (f:Function {{name: '{affected_function_name}'}})
    MERGE (b)-[:FIXED_IN {{status: '{status}'}}]->(f)
    """

    return ExplainableResult(
        result={
            "ticket_id": ticket_id,
            "status": status,
            "approved": approved_by_lead,
            "affected_function": affected_function_name,
            "message": "BugFix and RCA successfully registered in knowledge graph."
            if approved_by_lead else "BugFix recorded under PENDING_APPROVAL. Architectural lead review required before permanent indexing."
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation="Graph mutation: BugFix node creation linked to Function via FIXED_IN edge with approval gate."
    ).model_dump()
