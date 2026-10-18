"""
Code Domain Ownership Resolution and Email Approval Service for CodeGraph.
Resolves domain owners via .github/CODEOWNERS and dispatches approval emails.
Ingests approved BugFixes and Root Cause Analyses into FalkorDB upon email confirmation.
"""

import os
import json
import secrets
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any, Optional, List
from .config import settings
from .db import db
from .schema import Relationships, ExplainableResult

# In-memory audit outbox for test suites and offline local environments
SENT_APPROVAL_EMAILS: List[Dict[str, Any]] = []


def resolve_domain_owner(function_name: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """
    Resolves the Code Domain Owner for a given function or file path:
    1. Check Function node in graph if already indexed with domain_owner
    2. Check .github/CODEOWNERS or CODEOWNERS in project root
    3. Fallback to settings.code_domain_owner
    """
    clean_func = function_name.replace("func:", "") if function_name else None

    # 1. Check existing FunctionNode in DB
    if clean_func:
        fn_id = f"func:{clean_func}"
        node = db.memory_graph.nodes.get(fn_id)
        if node:
            props = node.get("properties", {})
            if props.get("domain_owner"):
                return props["domain_owner"]
            if not file_path and props.get("file_path"):
                file_path = props.get("file_path")

    # 2. Check CODEOWNERS files in repo
    codeowner_candidates = [
        Path(".github/CODEOWNERS"),
        Path("CODEOWNERS"),
        Path("docs/CODEOWNERS")
    ]

    for candidate in codeowner_candidates:
        if candidate.exists():
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
                fallback_wildcard = None
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        pattern = parts[0]
                        owner = parts[1]
                        if pattern == "*":
                            fallback_wildcard = owner
                        elif file_path and (pattern in file_path or file_path.endswith(pattern)):
                            return owner
                if fallback_wildcard:
                    return fallback_wildcard
            except Exception:
                pass

    # 3. Fallback to configured default domain owner
    return settings.code_domain_owner


def send_approval_email(
    to_email: str,
    ticket_id: str,
    symptom: str,
    rca: str,
    fix_summary: str,
    affected_function_name: str,
    approval_token: str
) -> Dict[str, Any]:
    """
    Dispatches an approval request email to the Code Domain Owner.
    Uses standard library smtplib when SMTP_HOST is configured,
    and logs to local audit outbox for offline testing.
    """
    subject = f"[Action Required] CodeGraph BugFix Approval Request: {ticket_id} ({affected_function_name})"
    approve_url = f"{settings.approval_base_url}/api/approve?ticket={ticket_id}&token={approval_token}&approver={to_email}"
    cli_cmd = f"uv run python -m codegraph approve-bugfix --ticket {ticket_id} --token {approval_token} --approver {to_email}"

    body_text = f"""Hello Code Domain Owner,

An AI Agent or engineer has submitted a production BugFix and Root Cause Analysis (RCA)
affecting code within your domain ({affected_function_name}).

Per CodeGraph Human-in-the-Loop Governance, your approval is required before this fix
is permanently ingested and indexed into the active knowledge graph.

--------------------------------------------------------------------------------
INCIDENT & PROPOSED FIX DETAILS:
--------------------------------------------------------------------------------
• Incident Ticket:     {ticket_id}
• Affected Function:   {affected_function_name}
• Error Symptom:       {symptom}
• Root Cause (RCA):    {rca}
• Action Taken / Fix:  {fix_summary}
• Approval Token:      {approval_token}

--------------------------------------------------------------------------------
HOW TO APPROVE & INGEST:
--------------------------------------------------------------------------------
Option 1: One-Click Email Approval Link:
  {approve_url}

Option 2: Terminal / CLI Approval:
  {cli_cmd}

Option 3: MCP Agent Tool Call:
  approve_bugfix_via_email(ticket_id="{ticket_id}", approval_token="{approval_token}")

Regards,
CodeGraph Operational Quality Assurance
"""

    email_record = {
        "to": to_email,
        "from": settings.smtp_from,
        "subject": subject,
        "ticket_id": ticket_id,
        "affected_function": affected_function_name,
        "approval_token": approval_token,
        "approve_url": approve_url,
        "cli_cmd": cli_cmd,
        "body_text": body_text
    }

    # Record to in-memory test outbox
    SENT_APPROVAL_EMAILS.append(email_record)

    # Optional local file audit
    try:
        outbox_file = Path(".codegraph_email_outbox.json")
        existing = []
        if outbox_file.exists():
            try:
                existing = json.loads(outbox_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.append(email_record)
        outbox_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Live SMTP dispatch if host is configured
    if settings.smtp_host:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from
            msg["To"] = to_email
            msg.set_content(body_text)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user and settings.smtp_password:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        except Exception as e:
            email_record["smtp_error"] = str(e)

    return {
        "dispatched": True,
        "to": to_email,
        "subject": subject,
        "approval_token": approval_token,
        "approve_url": approve_url
    }


def approve_bugfix_and_ingest(
    ticket_id: str,
    approval_token: str,
    approver_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates the domain owner's approval token and permanently ingests the BugFix and RCA into the database.
    Activates the (:Fix)-[:FIXES_FUNCTION {status: 'APPROVED'}]->(:Function) graph relationship.
    """
    fix_id = f"fix:{ticket_id}"
    fix_node = db.memory_graph.nodes.get(fix_id)

    if not fix_node:
        return ExplainableResult(
            result={"status": "ERROR", "message": f"Fix node '{fix_id}' not found in knowledge graph."},
            cypher_query="",
            traversal_path=[],
            explanation="Node lookup returned zero matches."
        ).model_dump()

    props = fix_node.get("properties", {})
    recorded_token = props.get("approval_token")
    current_status = props.get("approval_status")

    if current_status == "APPROVED":
        return ExplainableResult(
            result={
                "status": "ALREADY_APPROVED",
                "ticket_id": ticket_id,
                "approved_by": props.get("approved_by"),
                "message": f"BugFix for '{ticket_id}' was already approved and is actively indexed in the graph."
            },
            cypher_query="",
            traversal_path=[],
            explanation="Fix is already in APPROVED state."
        ).model_dump()

    # Validate approval token
    if not recorded_token or recorded_token != approval_token.strip():
        return ExplainableResult(
            result={
                "status": "REJECTED",
                "ticket_id": ticket_id,
                "message": "Invalid or expired approval token. Authorization denied."
            },
            cypher_query="",
            traversal_path=[],
            explanation="Token mismatch: Provided token does not match pending approval token."
        ).model_dump()

    # Activate approval
    final_approver = approver_email or props.get("domain_owner_email") or "domain_owner"
    props["approval_status"] = "APPROVED"
    props["approved_by"] = final_approver
    props["commit_hash"] = f"approved_{approval_token[:8]}"

    # Activate edge in graph
    affected_func_name = None
    for edge in db.memory_graph.edges:
        if edge["from"] == fix_id and edge["rel"] == Relationships.FIXES_FUNCTION:
            edge["properties"]["approval_status"] = "APPROVED"
            edge["properties"]["status"] = "APPROVED"
            target_fn = db.memory_graph.nodes.get(edge["to"])
            if target_fn:
                affected_func_name = target_fn.get("properties", {}).get("name")

    db.flush()

    cypher = f"""
    MATCH (fx:Fix {{id: '{fix_id}'}})
    SET fx.approval_status = 'APPROVED', fx.approved_by = '{final_approver}'
    WITH fx
    MATCH (fx)-[r:FIXES_FUNCTION]->(f:Function)
    SET r.approval_status = 'APPROVED', r.status = 'APPROVED'
    """

    return ExplainableResult(
        result={
            "ticket_id": ticket_id,
            "status": "APPROVED",
            "approved": True,
            "approved_by": final_approver,
            "affected_function": affected_func_name,
            "message": f"BugFix {ticket_id} has been verified by Code Domain Owner <{final_approver}> and successfully ingested into the knowledge graph."
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation="Graph mutation: Approval token verified. Status upgraded to APPROVED and FIXES_FUNCTION edge activated."
    ).model_dump()


def resolve_prd_owner(project_id: str = "project:payflow") -> str:
    """Resolves the PRD Owner for a given project from the graph or settings."""
    clean_pid = project_id if project_id.startswith("project:") else f"project:{project_id}"
    node = db.memory_graph.nodes.get(clean_pid)
    if node:
        owner = node.get("properties", {}).get("prd_owner")
        if owner:
            return owner

    # Check any project node
    for n in db.memory_graph.nodes.values():
        if n.get("label") == "Project":
            owner = n.get("properties", {}).get("prd_owner")
            if owner:
                return owner

    return settings.prd_owner


def send_prd_approval_email(
    to_email: str,
    project_id: str,
    feature_id: str,
    feature_title: str,
    description: str,
    priority: str,
    scenarios: List[str],
    guardrails: List[str],
    approval_token: str
) -> Dict[str, Any]:
    """
    Dispatches an approval request email to the PRD Owner.
    Includes feature specifications, test scenarios, and actionable approval links.
    """
    clean_fid = feature_id.replace("req:", "")
    subject = f"[Action Required] CodeGraph PRD Feature Approval: {clean_fid} ({feature_title})"
    approve_url = f"{settings.approval_base_url}/api/approve-prd?feature_id={clean_fid}&token={approval_token}&approver={to_email}"
    cli_cmd = f"uv run python -m codegraph approve-prd --feature-id {clean_fid} --token {approval_token} --approver {to_email}"

    scenarios_text = "\n".join([f"  • {s}" for s in scenarios]) if scenarios else "  (None provided)"
    guardrails_text = "\n".join([f"  • {g}" for g in guardrails]) if guardrails else "  (None provided)"

    body_text = f"""Hello PRD Owner,

An AI Agent has proposed a new feature and scenarios for Project '{project_id}':

--------------------------------------------------------------------------------
PROPOSED FEATURE SPECIFICATION:
--------------------------------------------------------------------------------
• Feature ID:     {clean_fid}
• Title:          {feature_title}
• Priority:       {priority}
• Description:    {description}

• Test Scenarios:
{scenarios_text}

• Guardrails:
{guardrails_text}

• Approval Token: {approval_token}

--------------------------------------------------------------------------------
HOW TO APPROVE & INGEST INTO KNOWLEDGE GRAPH:
--------------------------------------------------------------------------------
Option 1: One-Click Email Approval Link:
  {approve_url}

Option 2: Terminal / CLI Approval:
  {cli_cmd}

Option 3: MCP Agent Tool Call:
  approve_prd_update_via_email(feature_id="{clean_fid}", approval_token="{approval_token}")

Regards,
CodeGraph Product Governance Assistant
"""

    email_record = {
        "to": to_email,
        "from": settings.smtp_from,
        "subject": subject,
        "project_id": project_id,
        "feature_id": clean_fid,
        "approval_token": approval_token,
        "approve_url": approve_url,
        "cli_cmd": cli_cmd,
        "body_text": body_text
    }

    SENT_APPROVAL_EMAILS.append(email_record)

    if settings.smtp_host:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from
            msg["To"] = to_email
            msg.set_content(body_text)

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user and settings.smtp_password:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        except Exception as e:
            email_record["smtp_error"] = str(e)

    return {
        "dispatched": True,
        "to": to_email,
        "subject": subject,
        "approval_token": approval_token,
        "approve_url": approve_url
    }


def approve_prd_update_and_ingest(
    feature_id: str,
    approval_token: str,
    approver_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates the PRD Owner's approval token and permanently ingests the proposed feature and scenarios into FalkorDB.
    Activates the (:PRDInput)-[:SPECIFIES_REQUIREMENT]->(:FunctionalRequirement) and (:FunctionalRequirement)-[:HAS_SCENARIO]->(:Scenario) edges.
    """
    clean_fid = feature_id.replace("req:", "")
    req_id = f"req:{clean_fid}"
    req_node = db.memory_graph.nodes.get(req_id)

    if not req_node:
        return ExplainableResult(
            result={"status": "ERROR", "message": f"PRD requirement '{req_id}' not found in knowledge graph."},
            cypher_query="",
            traversal_path=[],
            explanation="Node lookup returned zero matches."
        ).model_dump()

    props = req_node.get("properties", {})
    recorded_token = props.get("approval_token")
    current_status = props.get("status")

    if current_status == "APPROVED" or current_status == "IMPLEMENTED":
        return ExplainableResult(
            result={
                "status": "ALREADY_APPROVED",
                "feature_id": clean_fid,
                "approved_by": props.get("approved_by"),
                "message": f"Feature '{clean_fid}' was already approved and is actively indexed in the graph."
            },
            cypher_query="",
            traversal_path=[],
            explanation="Feature is already in an approved state."
        ).model_dump()

    # Validate approval token
    if not recorded_token or recorded_token != approval_token.strip():
        return ExplainableResult(
            result={
                "status": "REJECTED",
                "feature_id": clean_fid,
                "message": "Invalid or expired PRD approval token. Authorization denied."
            },
            cypher_query="",
            traversal_path=[],
            explanation="Token mismatch: Provided token does not match pending PRD approval token."
        ).model_dump()

    final_approver = approver_email or props.get("prd_owner_email") or "prd_owner"
    props["status"] = "APPROVED"
    props["approved_by"] = final_approver

    # Activate edges to PRDInput and Scenarios
    for edge in db.memory_graph.edges:
        if edge["to"] == req_id and edge["rel"] == Relationships.SPECIFIES_REQUIREMENT:
            edge["properties"]["status"] = "APPROVED"
        if edge["from"] == req_id and edge["rel"] == Relationships.HAS_SCENARIO:
            edge["properties"]["status"] = "APPROVED"
            scen_node = db.memory_graph.nodes.get(edge["to"])
            if scen_node:
                scen_node["properties"]["status"] = "APPROVED"

    db.flush()

    cypher = f"""
    MATCH (r:FunctionalRequirement {{id: '{req_id}'}})
    SET r.status = 'APPROVED', r.approved_by = '{final_approver}'
    WITH r
    MATCH (pi:PRDInput)-[rel:SPECIFIES_REQUIREMENT]->(r)
    SET rel.status = 'APPROVED'
    """

    return ExplainableResult(
        result={
            "feature_id": clean_fid,
            "status": "APPROVED",
            "approved": True,
            "approved_by": final_approver,
            "message": f"Feature {clean_fid} ({props.get('title')}) and all accompanying scenarios have been approved by PRD Owner <{final_approver}> and successfully ingested into the knowledge graph."
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation="Graph mutation: PRD approval token verified. Status upgraded to APPROVED and SPECIFIES_REQUIREMENT / HAS_SCENARIO edges activated."
    ).model_dump()

