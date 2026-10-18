"""
Ingestion MCP Tools for CodeGraph.
Allows AI Agents and CI/CD pipelines to dynamically mutate and update the knowledge graph.
Includes an explicit human approval workflow for recording new BugFixes and Root Cause Analyses.
"""

import secrets
from typing import Dict, Any, Optional
from ..db import db
from ..schema import IssueNode, FixNode, Relationships, ExplainableResult
from ..ingest.code_parser import CodebaseParser
from ..ingest.prd_parser import PRDParser
from ..ingest.adr_parser import ADRParser
from ..ingest.change_tracker import ChangeTracker
from ..approval_service import resolve_domain_owner, send_approval_email, approve_bugfix_and_ingest
from ..iam import iam, Permission


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
    date: str = "2026-10-17",
    actor: Optional[str] = "payment-tech-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Records a resolved production bug, RCA, and verified fix into the Operations chain of the knowledge graph.
    Enforces the mandatory approval workflow and IAM permissions (requires MODIFY_CODEBASE).
    """
    clean_actor = actor or "payment-tech-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.MODIFY_CODEBASE, "record_bugfix")
    if denial:
        return denial
    clean_func = affected_function_name.replace("func:", "")
    issue_id = f"issue:{ticket_id}"
    fix_id = f"fix:{ticket_id}"

    domain_owner = resolve_domain_owner(function_name=clean_func)
    approval_token = secrets.token_hex(16) if not approved_by_lead else None
    status = "APPROVED" if approved_by_lead else "PENDING_APPROVAL"

    # Create Issue
    issue_node = IssueNode(
        id=issue_id,
        project_id="project:payflow",
        ticket=ticket_id,
        title=f"Incident {ticket_id}: {symptom}",
        symptom=symptom,
        severity="HIGH",
        reported_at=date
    )
    db.create_node(issue_id, "Issue", issue_node.model_dump())
    db.create_edge("project:payflow", Relationships.HAS_ISSUE, issue_id)

    # Create Fix
    fix_node = FixNode(
        id=fix_id,
        rca_id=f"rca:{ticket_id}",
        action_taken=fix_summary,
        commit_hash="pending" if not approved_by_lead else "approved_hash",
        approved_by="lead_reviewer" if approved_by_lead else "unapproved",
        approval_status=status,
        domain_owner_email=domain_owner,
        approval_token=approval_token
    )
    db.create_node(fix_id, "Fix", fix_node.model_dump())

    # Link to affected function
    target_fn_id = f"func:{clean_func}"
    if target_fn_id in db.memory_graph.nodes:
        db.create_edge(issue_id, Relationships.MANIFESTED_IN_FUNCTION, target_fn_id)
        db.create_edge(fix_id, Relationships.FIXES_FUNCTION, target_fn_id, {"approval_status": status})

    db.flush()

    # If unapproved, dispatch email to the Code Domain Owner
    email_dispatched = False
    if not approved_by_lead:
        email_res = send_approval_email(
            to_email=domain_owner,
            ticket_id=ticket_id,
            symptom=symptom,
            rca=rca,
            fix_summary=fix_summary,
            affected_function_name=clean_func,
            approval_token=approval_token
        )
        email_dispatched = email_res.get("dispatched", False)

    cypher = f"""
    MERGE (i:Issue {{id: '{issue_id}'}})
    SET i.symptom = '{symptom}', i.approved = {str(approved_by_lead).lower()}
    MERGE (fx:Fix {{id: '{fix_id}'}})
    SET fx.action_taken = '{fix_summary}', fx.approval_status = '{status}'
    WITH i, fx
    MATCH (f:Function {{name: '{clean_func}'}})
    MERGE (i)-[:MANIFESTED_IN_FUNCTION]->(f)
    MERGE (fx)-[:FIXES_FUNCTION {{status: '{status}'}}]->(f)
    """

    msg = (
        "BugFix and RCA successfully registered in knowledge graph Operations chain."
        if approved_by_lead
        else f"Approval request dispatched to Code Domain Owner <{domain_owner}> via email. Fix recorded under PENDING_APPROVAL and will be ingested once approved."
    )

    return ExplainableResult(
        result={
            "ticket_id": ticket_id,
            "status": status,
            "approved": approved_by_lead,
            "domain_owner": domain_owner,
            "approval_token": approval_token,
            "email_dispatched": email_dispatched,
            "affected_function": clean_func,
            "message": msg
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation="Graph mutation: Issue and Fix node creation linked to Function via MANIFESTED_IN_FUNCTION and FIXES_FUNCTION."
    ).model_dump()


def approve_bugfix_via_email(
    ticket_id: str,
    approval_token: str,
    approver_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Approves a pending BugFix using the secure token received via email and ingests it into FalkorDB.
    Activates the (:Fix)-[:FIXES_FUNCTION {status: 'APPROVED'}]->(:Function) edge.
    """
    return approve_bugfix_and_ingest(
        ticket_id=ticket_id,
        approval_token=approval_token,
        approver_email=approver_email
    )

