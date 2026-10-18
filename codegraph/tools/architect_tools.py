"""
Architect Persona and Architectural Governance Tools.
Provides Architectural Decision Records (ADRs) authoring, proposal lifecycle management,
and Architect human-in-the-loop email approval workflows across the 5-Pillar Connected Knowledge Graph.
"""

import secrets
from typing import Dict, Any, Optional, List

from ..db import db
from ..schema import DecisionNode, ArchitectureNode, Relationships, ExplainableResult, TraversalStep
from ..approval_service import (
    resolve_architect_owner,
    send_architect_approval_email,
    approve_architectural_proposal_and_ingest
)
from ..iam import iam, Permission, Role


def propose_architectural_change(
    decision_id: str,
    pattern_name: str,
    decision_statement: str,
    rationale: str,
    invariants: str = "",
    project_id: str = "project:payflow",
    adr_req_id: Optional[str] = None,
    actor: Optional[str] = "developer@payflow.internal",
    approved_by_architect: bool = False
) -> Dict[str, Any]:
    """
    Proposes or authors a new architectural decision (ADR) in the knowledge graph.
    - Developers can propose changes, which are staged under PENDING_APPROVAL and dispatch an approval email to the Lead Architect.
    - Architects with AUTHOR_ARCHITECTURE permission can directly author or approve immediately.
    - Unauthorized personas (Product Managers, Program Managers without permission) are rejected by IAM.
    """
    clean_actor = actor or "developer@payflow.internal"

    # Enforce IAM permission
    if approved_by_architect:
        denial = iam.enforce_permission(clean_actor, Permission.AUTHOR_ARCHITECTURE, "author_architectural_change")
        if denial:
            return denial
    else:
        denial = iam.enforce_permission(clean_actor, Permission.PROPOSE_ARCHITECTURE, "propose_architectural_change")
        if denial:
            return denial

    clean_pid = project_id if project_id.startswith("project:") else f"project:{project_id}"
    architect_owner = resolve_architect_owner(clean_pid)

    clean_did = decision_id.replace("decision:", "")
    did = f"decision:{clean_did}"

    approval_token = secrets.token_hex(16) if not approved_by_architect else None
    status = "APPROVED" if approved_by_architect else "PENDING_APPROVAL"
    approved_by = clean_actor if approved_by_architect else None

    # Resolve or create Architecture pattern node
    clean_pat = pattern_name.lower().replace(" ", "_").replace("-", "_")
    arch_id = f"arch:{clean_pat}"
    if arch_id not in db.memory_graph.nodes:
        parent_req = adr_req_id or "adr_req:external_network_resilience"
        arch_node = ArchitectureNode(
            id=arch_id,
            adr_req_id=parent_req,
            pattern_name=pattern_name,
            description=f"Architectural pattern for {pattern_name}"
        )
        db.create_node(arch_id, "Architecture", arch_node.model_dump())
        if parent_req in db.memory_graph.nodes:
            db.create_edge(parent_req, Relationships.DEFINES_ARCHITECTURE, arch_id)

    # Create / Stage DecisionNode
    adr_prefix = clean_did.split(":")[0] if ":" in clean_did else clean_did
    dec_node = DecisionNode(
        id=did,
        arch_id=arch_id,
        adr_id=adr_prefix,
        title=f"Decision for {pattern_name}",
        statement=decision_statement,
        rationale=rationale,
        invariants=invariants,
        status=status,
        proposed_by=clean_actor,
        approved_by=approved_by,
        approval_token=approval_token,
        architect_owner_email=architect_owner
    )
    db.create_node(did, "Decision", dec_node.model_dump())
    db.create_edge(arch_id, Relationships.LEADS_TO_DECISION, did, {"status": status})
    db.flush()

    # Dispatch email if pending architect review
    email_dispatched = False
    if not approved_by_architect:
        email_res = send_architect_approval_email(
            to_email=architect_owner,
            project_id=clean_pid,
            decision_id=clean_did,
            decision_statement=decision_statement,
            rationale=rationale,
            invariants=invariants,
            pattern_name=pattern_name,
            proposed_by=clean_actor,
            approval_token=approval_token
        )
        email_dispatched = email_res.get("dispatched", False)

    cypher = f"""
    MERGE (a:Architecture {{id: '{arch_id}'}})
    MERGE (d:Decision {{id: '{did}'}})
    SET d.statement = '{decision_statement}', d.status = '{status}', d.proposed_by = '{clean_actor}'
    MERGE (a)-[r:LEADS_TO_DECISION {{status: '{status}'}}]->(d)
    """

    msg = (
        f"Architectural decision {clean_did} authored and approved by Architect <{clean_actor}>."
        if approved_by_architect
        else f"Architectural proposal {clean_did} submitted by <{clean_actor}>. Approval request dispatched to Lead Systems Architect <{architect_owner}> via email."
    )

    return ExplainableResult(
        result={
            "decision_id": clean_did,
            "status": status,
            "approved": approved_by_architect,
            "proposed_by": clean_actor,
            "architect_owner": architect_owner,
            "approval_token": approval_token,
            "email_dispatched": email_dispatched,
            "message": msg
        },
        cypher_query=cypher.strip(),
        traversal_path=[
            TraversalStep(
                from_node=arch_id,
                relationship=Relationships.LEADS_TO_DECISION,
                to_node=did,
                explanation=f"Architecture '{pattern_name}' links to Decision '{clean_did}' with status '{status}'"
            )
        ],
        explanation="Graph mutation: Proposed architectural decision created and linked via LEADS_TO_DECISION."
    ).model_dump()


def approve_architectural_proposal_via_email(
    decision_id: str,
    approval_token: str,
    actor: Optional[str] = "architect-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Validates the Architect's approval token and permanently ingests the proposed architectural decision into the graph.
    Enforces that only actors with AUTHOR_ARCHITECTURE permission can approve architectural decisions.
    """
    clean_actor = actor or "architect-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.AUTHOR_ARCHITECTURE, "approve_architectural_proposal_via_email")
    if denial:
        return denial

    return approve_architectural_proposal_and_ingest(
        decision_id=decision_id,
        approval_token=approval_token,
        approver_email=clean_actor
    )
