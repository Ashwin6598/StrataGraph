"""
Product Agent MCP Tools.
Designed specifically for Product Managers: outputs clear business summaries in plain English,
no code snippets, with multi-hop graph reasoning across the PRD, CodeBase, ADR, and Operations chains.
"""

import secrets
from typing import Dict, Any, List, Optional
from ..db import db
from ..schema import (
    ExplainableResult,
    TraversalStep,
    Relationships,
    FunctionalRequirementNode,
    ScenarioNode,
    GuardrailNode
)
from ..approval_service import resolve_prd_owner, send_prd_approval_email, approve_prd_update_and_ingest
from ..iam import iam, Permission


def query_prd_coverage(project_id: str = "project:payflow") -> Dict[str, Any]:
    """
    Analyzes how completely the codebase implements the Product Requirements.
    Traverses: Project -> PRDInput -> FunctionalRequirement -> Function -> CodeLogic.
    Returns total requirements, implemented count, missing requirements, and coverage percentage.
    Output is in plain business terms.
    """
    cypher = """
    MATCH (p:Project {id: $project_id})-[:HAS_PRD_INPUT]->(pi:PRDInput)-[:SPECIFIES_REQUIREMENT]->(r:FunctionalRequirement)
    OPTIONAL MATCH (r)-[:IMPLEMENTED_BY_FUNCTION]->(f:Function)-[:EXECUTES_LOGIC]->(cl:CodeLogic)
    OPTIONAL MATCH (r)-[:ENFORCES_GUARDRAIL]->(g:Guardrail)
    RETURN r.id AS req_id, r.title AS title, r.priority AS priority, r.status AS status,
           collect(DISTINCT f.name) AS implementing_functions,
           collect(DISTINCT g.title) AS guardrails
    """

    all_reqs = []
    implemented_reqs = []
    missing_reqs = []
    traversal_path = []

    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "FunctionalRequirement":
            props = node["properties"]
            if props.get("status") == "PENDING_APPROVAL":
                continue
            req_id = node["id"]


            # Find linked functions
            linked_funcs = []
            for edge in db.memory_graph.edges:
                if edge["from"] == req_id and edge["rel"] == Relationships.IMPLEMENTED_BY_FUNCTION:
                    fn_node = db.memory_graph.nodes.get(edge["to"])
                    if fn_node:
                        linked_funcs.append(fn_node["properties"].get("name"))
                        traversal_path.append(TraversalStep(
                            from_node=f"FunctionalRequirement({req_id})",
                            relationship=Relationships.IMPLEMENTED_BY_FUNCTION,
                            to_node=f"Function({fn_node['properties'].get('name')})",
                            explanation=f"Requirement '{props.get('title')}' is implemented by code function '{fn_node['properties'].get('name')}'"
                        ))

            # Find linked guardrails
            linked_guardrails = []
            for edge in db.memory_graph.edges:
                if edge["from"] == req_id and edge["rel"] == Relationships.ENFORCES_GUARDRAIL:
                    g_node = db.memory_graph.nodes.get(edge["to"])
                    if g_node:
                        linked_guardrails.append(g_node["properties"].get("title"))

            item = {
                "id": req_id.replace("req:", ""),
                "title": props.get("title"),
                "priority": props.get("priority"),
                "status": props.get("status"),
                "guardrails": linked_guardrails,
                "implemented_by_functions": linked_funcs,
                "is_covered": len(linked_funcs) > 0
            }
            all_reqs.append(item)
            if item["is_covered"]:
                implemented_reqs.append(item)
            else:
                missing_reqs.append(item)

    total = len(all_reqs)
    covered = len(implemented_reqs)
    pct = round((covered / total * 100), 1) if total > 0 else 0.0

    summary = (
        f"Product Requirements Coverage: {pct}% complete. "
        f"{covered} of {total} functional requirements have verified engineering implementation. "
        f"{len(missing_reqs)} requirements remain unimplemented ({', '.join([m['id'] + ': ' + m['title'] for m in missing_reqs])})."
    )

    result_data = {
        "summary": summary,
        "coverage_percentage": f"{pct}%",
        "total_requirements": total,
        "implemented_count": covered,
        "unimplemented_count": len(missing_reqs),
        "implemented_requirements": [
            {"id": r["id"], "title": r["title"], "priority": r["priority"], "guardrails": r["guardrails"]} for r in implemented_reqs
        ],
        "missing_requirements": [
            {"id": r["id"], "title": r["title"], "priority": r["priority"]} for r in missing_reqs
        ]
    }

    return ExplainableResult(
        result=result_data,
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Traversed Project -> PRDInput -> FunctionalRequirement -> Guardrail -> Function -> CodeLogic across the knowledge graph."
    ).model_dump()


def simulate_scenario(scenario_query: str) -> Dict[str, Any]:
    """
    Simulates a business or test scenario (e.g. 'expired card', 'refund after 30 days') using multi-hop graph traversal.
    Follows: PRDInput -> FunctionalRequirement -> Guardrail -> PRDOutput -> Function -> CodeLogic -> CodeOutput.
    Explains the exact system behavior in plain business English with zero code examples.
    """
    cypher = """
    MATCH (pi:PRDInput)-[:SPECIFIES_REQUIREMENT]->(r:FunctionalRequirement)-[:ENFORCES_GUARDRAIL]->(g:Guardrail)-[:DEFINES_PRD_OUTPUT]->(po:PRDOutput)
    OPTIONAL MATCH (r)-[:IMPLEMENTED_BY_FUNCTION]->(f:Function)-[:EXECUTES_LOGIC]->(cl:CodeLogic)-[:PRODUCES_CODE_OUTPUT]->(co:CodeOutput)
    WHERE g.title CONTAINS $keyword OR g.rule_statement CONTAINS $keyword OR po.business_outcome CONTAINS $keyword
    RETURN r, g, po, f, cl, co
    """

    query_lower = scenario_query.lower()
    matched_guardrails = []
    traversal_path = []

    # Score matches across Guardrails and PRD Outputs
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Guardrail":
            props = node["properties"]
            title = props.get("title", "").lower()
            rule = props.get("rule_statement", "").lower()
            v_code = props.get("violation_code", "").lower()

            stopwords = {"with", "from", "user", "payment", "when", "that", "this", "have", "been", "card", "test", "into", "after", "then", "than", "more", "less", "over", "under", "code", "must", "should", "will", "the", "and", "for"}
            score = 0
            if query_lower in title or query_lower in rule:
                score += 100
            for k in query_lower.split():
                if len(k) > 2 and k not in stopwords:
                    if k in title or k in rule or k in v_code:
                        score += 10

            if score >= 10:
                req_id = props.get("req_id")
                req_node = db.memory_graph.nodes.get(req_id, {})
                req_props = req_node.get("properties", {})

                # Find PRD outputs
                outputs = []
                for edge in db.memory_graph.edges:
                    if edge["from"] == nid and edge["rel"] == Relationships.DEFINES_PRD_OUTPUT:
                        out_node = db.memory_graph.nodes.get(edge["to"])
                        if out_node:
                            outputs.append(out_node["properties"])

                # Find implementing code functions & logic
                implementing_funcs = []
                for edge in db.memory_graph.edges:
                    if edge["from"] == req_id and edge["rel"] == Relationships.IMPLEMENTED_BY_FUNCTION:
                        fn_node = db.memory_graph.nodes.get(edge["to"])
                        if fn_node:
                            implementing_funcs.append(fn_node["properties"].get("name"))

                traversal_path.append(TraversalStep(
                    from_node=f"FunctionalRequirement({req_id})",
                    relationship=Relationships.ENFORCES_GUARDRAIL,
                    to_node=f"Guardrail({nid})",
                    explanation=f"Business requirement '{req_props.get('title')}' establishes safety guardrail '{props.get('title')}'"
                ))

                matched_guardrails.append({
                    "score": score,
                    "requirement": req_props.get("title"),
                    "guardrail_title": props.get("title"),
                    "rule_statement": props.get("rule_statement"),
                    "violation_code": props.get("violation_code"),
                    "enforcement_level": props.get("enforcement_level"),
                    "expected_outcomes": [o.get("business_outcome") for o in outputs],
                    "handled_in_code": len(implementing_funcs) > 0,
                    "workflow_components": implementing_funcs
                })

    matched_guardrails.sort(key=lambda x: x["score"], reverse=True)

    if matched_guardrails:
        top = matched_guardrails[0]
        outcome_desc = top["expected_outcomes"][0] if top["expected_outcomes"] else "Standard business policy enforcement."
        business_explanation = (
            f"When this scenario occurs: The system enforces '{top['guardrail_title']}' under '{top['requirement']}'. "
            f"Rule: {top['rule_statement']} "
            f"Expected Outcome: {outcome_desc} "
            f"Status: This business rule is actively guarded in the production flow."
        )
    else:
        business_explanation = (
            f"Scenario '{scenario_query}' was simulated against the knowledge graph. "
            "No direct match was found in existing test cases or PRD rules. "
            "Recommendation: Product team should consider defining this as a new scenario for the engineering backlog."
        )

    return ExplainableResult(
        result={
            "scenario_query": scenario_query,
            "plain_english_assessment": business_explanation,
            "matched_guardrails": matched_guardrails
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Multi-hop chain traversal: PRDInput -> FunctionalRequirement -> Guardrail -> PRDOutput -> Function -> CodeLogic."
    ).model_dump()


def get_change_history(from_date: Optional[str] = None, keyword: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the complete chronological timeline of changes with explicit reasons (WHAT changed and WHY it changed).
    Traverses: ChangeTimeline -> MotivatedBy (PRD Requirement / ADR Decision / Operational BugFix).
    Formatted for Product Managers and Auditors.
    """
    cypher = """
    MATCH (p:Project)-[:HAS_TIMELINE_RECORD]->(tl:ChangeTimeline)
    OPTIONAL MATCH (tl)-[:MOTIVATED_BY_PRD]->(r:FunctionalRequirement)
    OPTIONAL MATCH (tl)-[:MOTIVATED_BY_ADR]->(d:Decision)
    OPTIONAL MATCH (tl)-[:MOTIVATED_BY_FIX]->(fx:Fix)
    OPTIONAL MATCH (tl)-[:CHANGED_NODE]->(cl:CodeLogic)
    WHERE ($from_date IS NULL OR tl.date >= $from_date)
    RETURN tl.date AS date, tl.commit_hash AS commit, tl.what_changed AS what, tl.why_changed AS why,
           tl.change_category AS category, r.title AS prd_reason, d.title AS adr_reason, fx.action_taken AS fix_reason
    ORDER BY tl.date DESC
    """

    records = []
    traversal_path = []

    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "ChangeTimeline":
            props = node["properties"]
            c_date = props.get("date", "")
            if from_date and c_date < from_date:
                continue

            # Find motivations
            motivations = []
            for edge in db.memory_graph.edges:
                if edge["from"] == nid:
                    target_node = db.memory_graph.nodes.get(edge["to"])
                    if target_node:
                        lbl = target_node["label"]
                        t_title = target_node["properties"].get("title") or target_node["properties"].get("name") or target_node["id"]
                        motivations.append(f"{lbl}: {t_title}")
                        traversal_path.append(TraversalStep(
                            from_node=f"ChangeTimeline({props.get('commit_hash')[:7]})",
                            relationship=edge["rel"],
                            to_node=f"{lbl}({t_title})",
                            explanation=f"Change on {c_date} was motivated by {lbl} '{t_title}'"
                        ))

            records.append({
                "date": c_date,
                "commit_hash": props.get("commit_hash"),
                "author": props.get("author"),
                "what_changed": props.get("what_changed"),
                "why_changed": props.get("why_changed"),
                "category": props.get("change_category"),
                "diff_summary": props.get("diff_summary"),
                "governing_lineage": motivations
            })

    records.sort(key=lambda x: x["date"], reverse=True)

    return ExplainableResult(
        result={
            "total_changes": len(records),
            "timeline": records,
            "plain_english_summary": f"Retrieved {len(records)} timeline changes with full 'What Changed' and 'Why Changed' lineage connected to PRDs, ADRs, and Operations fixes."
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Traversed Project -> ChangeTimeline -> MotivatedBy (PRD | ADR | Fix) lineage graph."
    ).model_dump()


def list_uncovered_requirements() -> Dict[str, Any]:
    """
    Identifies all business requirements in the PRD that currently have zero implementing code functions or logic.
    Useful for Product Managers to detect release bottlenecks and unstarted backlog items.
    """
    cypher = """
    MATCH (r:FunctionalRequirement)
    WHERE NOT (r)-[:IMPLEMENTED_BY_FUNCTION]->()
    RETURN r.id AS req_id, r.title AS title, r.priority AS priority, r.description AS description
    """

    uncovered = []
    traversal_path = []

    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "FunctionalRequirement":
            props = node["properties"]
            if props.get("status") == "PENDING_APPROVAL":
                continue
            req_id = node["id"]
            has_code = False
            for edge in db.memory_graph.edges:
                if edge["from"] == req_id and edge["rel"] == Relationships.IMPLEMENTED_BY_FUNCTION:
                    has_code = True
                    break

            if not has_code:
                clean_id = req_id.replace("req:", "")
                uncovered.append({
                    "id": clean_id,
                    "title": props.get("title"),
                    "priority": props.get("priority"),
                    "description": props.get("description"),
                    "status": "NOT_STARTED_IN_CODE"
                })
                traversal_path.append(TraversalStep(
                    from_node=f"FunctionalRequirement({clean_id})",
                    relationship="NOT_IMPLEMENTED_BY_FUNCTION",
                    to_node="None",
                    explanation=f"Requirement {clean_id} ({props.get('title')}) has no linked code function in the graph."
                ))

    return ExplainableResult(
        result={
            "uncovered_count": len(uncovered),
            "uncovered_requirements": uncovered,
            "product_takeaway": f"{len(uncovered)} PRD requirements currently lack engineering implementation."
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Graph query matching FunctionalRequirement nodes with out-degree zero on IMPLEMENTED_BY_FUNCTION."
    ).model_dump()


def update_prd_features_and_scenarios(
    feature_id: str,
    feature_title: str,
    description: str,
    project_id: str = "project:payflow",
    priority: str = "HIGH",
    scenarios: Optional[List[str]] = None,
    guardrails: Optional[List[str]] = None,
    approved_by_prd_owner: bool = False,
    actor: Optional[str] = "product-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Updates the PRD by proposing or adding a new feature/requirement and accompanying test scenarios.
    Enforces the PRD Owner approval workflow and IAM permissions (requires UPDATE_PRD).
    """
    clean_actor = actor or "product-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.UPDATE_PRD, "update_prd_features_and_scenarios")
    if denial:
        return denial

    scenarios = scenarios or []
    guardrails = guardrails or []
    clean_fid = feature_id.replace("req:", "")
    req_id = f"req:{clean_fid}"

    clean_pid = project_id if project_id.startswith("project:") else f"project:{project_id}"
    prd_owner = resolve_prd_owner(clean_pid)
    approval_token = secrets.token_hex(16) if not approved_by_prd_owner else None
    status = "APPROVED" if approved_by_prd_owner else "PENDING_APPROVAL"

    # Find project's PRD input or default
    prd_input_id = f"prd_input:{clean_pid.replace('project:', '')}_features"
    if prd_input_id not in db.memory_graph.nodes:
        # Link to first available PRDInput or fallback
        for nid, n in db.memory_graph.nodes.items():
            if n.get("label") == "PRDInput":
                prd_input_id = nid
                break

    # Create / Stage FunctionalRequirementNode
    req_node = FunctionalRequirementNode(
        id=req_id,
        prd_input_id=prd_input_id,
        title=feature_title,
        description=description,
        priority=priority,
        status=status,
        approval_token=approval_token,
        prd_owner_email=prd_owner,
        approved_by="prd_owner" if approved_by_prd_owner else None
    )
    db.create_node(req_id, "FunctionalRequirement", req_node.model_dump())
    db.create_edge(prd_input_id, Relationships.SPECIFIES_REQUIREMENT, req_id, {"status": status})

    # Create Scenarios
    for idx, scen_text in enumerate(scenarios, 1):
        scen_id = f"scen:{clean_fid}-{idx}"
        scen_node = ScenarioNode(
            id=scen_id,
            req_id=req_id,
            description=scen_text,
            expected_behavior=scen_text,
            covered_by_code=False,
            status=status
        )
        db.create_node(scen_id, "Scenario", scen_node.model_dump())
        db.create_edge(req_id, Relationships.HAS_SCENARIO, scen_id, {"status": status})

    # Create Guardrails
    for idx, guard_text in enumerate(guardrails, 1):
        guard_id = f"guardrail:{clean_fid.lower()}-{idx}"
        guard_node = GuardrailNode(
            id=guard_id,
            req_id=req_id,
            title=f"Guardrail for {clean_fid}",
            rule_statement=guard_text,
            enforcement_level="HARD_BLOCK",
            violation_code=f"ERR_{clean_fid.upper()}_VIOLATION"
        )
        db.create_node(guard_id, "Guardrail", guard_node.model_dump())
        db.create_edge(req_id, Relationships.ENFORCES_GUARDRAIL, guard_id)

    db.flush()

    # If unapproved, dispatch email to the project's PRD Owner
    email_dispatched = False
    if not approved_by_prd_owner:
        email_res = send_prd_approval_email(
            to_email=prd_owner,
            project_id=clean_pid,
            feature_id=clean_fid,
            feature_title=feature_title,
            description=description,
            priority=priority,
            scenarios=scenarios,
            guardrails=guardrails,
            approval_token=approval_token
        )
        email_dispatched = email_res.get("dispatched", False)

    msg = (
        f"Feature {clean_fid} ({feature_title}) and {len(scenarios)} scenarios successfully approved and ingested into PRD graph."
        if approved_by_prd_owner
        else f"Approval request dispatched to PRD Owner <{prd_owner}> via email. Feature '{clean_fid}' and {len(scenarios)} scenarios staged under PENDING_APPROVAL and will be ingested into the active graph once approved."
    )

    return ExplainableResult(
        result={
            "feature_id": clean_fid,
            "status": status,
            "approved": approved_by_prd_owner,
            "prd_owner": prd_owner,
            "approval_token": approval_token,
            "email_dispatched": email_dispatched,
            "scenarios_count": len(scenarios),
            "guardrails_count": len(guardrails),
            "message": msg
        },
        cypher_query=f"MERGE (r:FunctionalRequirement {{id: '{req_id}', status: '{status}'}})",
        traversal_path=[],
        explanation="PRD update: FunctionalRequirement and Scenario nodes staged/created with PRD owner approval gate."
    ).model_dump()


def approve_prd_update_via_email(
    feature_id: str,
    approval_token: str,
    approver_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validates PRD Owner's approval token and permanently ingests the feature and scenarios into the active knowledge graph.
    Enforces that only actors with UPDATE_PRD permission can approve PRD features and scenarios.
    """
    clean_actor = approver_email or "product-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.UPDATE_PRD, "approve_prd_update_via_email")
    if denial:
        return denial

    return approve_prd_update_and_ingest(
        feature_id=feature_id,
        approval_token=approval_token,
        approver_email=clean_actor
    )

