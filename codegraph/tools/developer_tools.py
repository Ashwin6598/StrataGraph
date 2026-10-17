"""
Developer Agent MCP Tools.
Designed for Software Engineers: outputs detailed technical root causes, file paths, line numbers,
ADR constraints, and code-level remediation steps across the 4-Pillar Graph.
"""

from typing import Dict, Any, List, Optional
from ..db import db
from ..schema import ExplainableResult, TraversalStep, Relationships


def debug_issue(error_logs: str) -> Dict[str, Any]:
    """
    Analyzes application error logs or incident symptoms (e.g., 'REFUND_TIMEOUT', 'CASCADE_FRAUD_CHECK_FAILURES').
    Traverses: Project -> Issue -> RCA -> Fix -> OpResult -> Function -> CodeLogic -> Decision.
    Returns technical Root Cause Analysis (RCA), affected files/lines, violated ADRs, and verified resolution steps.
    """
    cypher = """
    MATCH (i:Issue)
    WHERE i.symptom CONTAINS $error OR i.title CONTAINS $error OR i.ticket CONTAINS $error
    OPTIONAL MATCH (i)-[:ANALYZED_BY_RCA]->(rca:RCA)-[:RESOLVED_BY_FIX]->(fx:Fix)-[:ACHIEVES_RESULT]->(res:OpResult)
    OPTIONAL MATCH (i)-[:MANIFESTED_IN_FUNCTION]->(f:Function)-[:EXECUTES_LOGIC]->(cl:CodeLogic)
    OPTIONAL MATCH (i)-[:VIOLATED_DECISION]->(d:Decision)
    RETURN i, rca, fx, res, f, cl, d
    """

    error_lower = error_logs.lower()
    matches = []
    traversal_path = []

    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Issue":
            props = node["properties"]
            symptom = props.get("symptom", "").lower()
            title = props.get("title", "").lower()
            ticket = props.get("ticket", "")

            # Match symptoms or error keywords
            error_keywords = [w for w in error_lower.replace("_", " ").split() if len(w) > 3]
            matched = any(k in symptom or k in title for k in error_keywords) or (ticket.lower() in error_lower)

            if matched:
                # Find RCA
                rca_data = None
                fix_data = None
                for edge in db.memory_graph.edges:
                    if edge["from"] == nid and edge["rel"] == Relationships.ANALYZED_BY_RCA:
                        rca_node = db.memory_graph.nodes.get(edge["to"])
                        if rca_node:
                            rca_data = rca_node["properties"]
                            traversal_path.append(TraversalStep(
                                from_node=f"Issue({ticket})",
                                relationship=Relationships.ANALYZED_BY_RCA,
                                to_node=f"RCA({edge['to']})",
                                explanation=f"Incident {ticket} investigated with Root Cause Analysis '{edge['to']}'"
                            ))

                            # Find Fix
                            for f_edge in db.memory_graph.edges:
                                if f_edge["from"] == edge["to"] and f_edge["rel"] == Relationships.RESOLVED_BY_FIX:
                                    fix_node = db.memory_graph.nodes.get(f_edge["to"])
                                    if fix_node:
                                        fix_data = fix_node["properties"]
                                        traversal_path.append(TraversalStep(
                                            from_node=f"RCA({edge['to']})",
                                            relationship=Relationships.RESOLVED_BY_FIX,
                                            to_node=f"Fix({f_edge['to']})",
                                            explanation=f"RCA resolved by engineering fix '{fix_node['properties'].get('action_taken')}'"
                                        ))

                # Find Manifested Function & CodeLogic
                target_funcs = []
                for edge in db.memory_graph.edges:
                    if edge["from"] == nid and edge["rel"] == Relationships.MANIFESTED_IN_FUNCTION:
                        fn_node = db.memory_graph.nodes.get(edge["to"])
                        if fn_node:
                            target_funcs.append(fn_node["properties"])
                            traversal_path.append(TraversalStep(
                                from_node=f"Issue({ticket})",
                                relationship=Relationships.MANIFESTED_IN_FUNCTION,
                                to_node=f"Function({fn_node['properties'].get('name')})",
                                explanation=f"Incident {ticket} manifested in function '{fn_node['properties'].get('name')}'"
                            ))

                # Find Violated Decision
                violated_decisions = []
                for edge in db.memory_graph.edges:
                    if edge["from"] == nid and edge["rel"] == Relationships.VIOLATED_DECISION:
                        d_node = db.memory_graph.nodes.get(edge["to"])
                        if d_node:
                            violated_decisions.append(d_node["properties"])
                            traversal_path.append(TraversalStep(
                                from_node=f"Issue({ticket})",
                                relationship=Relationships.VIOLATED_DECISION,
                                to_node=f"Decision({d_node['properties'].get('title')})",
                                explanation=f"Incident violated architectural decision '{d_node['properties'].get('title')}'"
                            ))

                matches.append({
                    "ticket_id": ticket,
                    "title": props.get("title"),
                    "symptom": props.get("symptom"),
                    "root_cause_analysis": rca_data.get("root_cause") if rca_data else "RCA pending investigation.",
                    "trigger_condition": rca_data.get("trigger_condition") if rca_data else "Under peak load.",
                    "action_taken": fix_data.get("action_taken") if fix_data else "Follow standard recovery.",
                    "violated_adr": [d.get("adr_id") + ": " + d.get("title") for d in violated_decisions],
                    "affected_code_locations": [
                        {
                            "function": f.get("name"),
                            "file": f.get("file_path"),
                            "lines": f"{f.get('line_start')}-{f.get('line_end')}"
                        } for f in target_funcs
                    ]
                })

    if not matches:
        summary = f"No direct historical Issue match found in knowledge graph for '{error_logs}'. Search runbooks or initiate new RCA."
    else:
        top = matches[0]
        code_loc = top["affected_code_locations"][0] if top["affected_code_locations"] else {"file": "unknown", "lines": "unknown"}
        adr_info = f" (Violated: {', '.join(top['violated_adr'])})" if top["violated_adr"] else ""
        summary = (
            f"🚨 Match Identified: {top['ticket_id']}{adr_info}\n"
            f"• Symptom: {top['symptom']}\n"
            f"• Root Cause Analysis (RCA): {top['root_cause_analysis']}\n"
            f"• Target Code: {code_loc.get('file')} (lines {code_loc.get('lines')})\n"
            f"• Verified Fix: {top['action_taken']}"
        )

    return ExplainableResult(
        result={
            "matched_incidents": matches,
            "technical_diagnostic_summary": summary
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Graph traversal: Issue -> RCA -> Fix -> Function -> CodeLogic -> Decision (ADR)."
    ).model_dump()


def check_safe_to_change(function_name: str, proposed_change: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluates whether modifying a function is safe by traversing:
    Function <- Decision (ADR) <- Architecture <- ADRRequirement <- FunctionalRequirement
    + Historical Issues and Regressions.
    """
    cypher = """
    MATCH (f:Function)
    WHERE f.name = $function_name OR f.id = $function_name
    OPTIONAL MATCH (dec:Decision)-[:CONSTRAINS_FUNCTION]->(f)
    OPTIONAL MATCH (f)<-[:MANIFESTED_IN_FUNCTION]-(iss:Issue)-[:ANALYZED_BY_RCA]->(rca:RCA)
    OPTIONAL MATCH (r:FunctionalRequirement)-[:IMPLEMENTED_BY_FUNCTION]->(f)
    OPTIONAL MATCH (f)-[:EXECUTES_LOGIC]->(cl:CodeLogic)
    RETURN f, collect(DISTINCT dec) AS decisions, collect(DISTINCT iss) AS past_issues,
           collect(DISTINCT r) AS prd_requirements, collect(DISTINCT cl) AS logics
    """

    fn_node_id = None
    fn_props = None
    clean_name = function_name.replace("func:", "")

    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Function" and (node["properties"].get("name") == clean_name or node["id"] == function_name):
            fn_node_id = nid
            fn_props = node["properties"]
            break

    if not fn_node_id:
        return ExplainableResult(
            result={"safe": False, "error": f"Function '{function_name}' not found in knowledge graph."},
            cypher_query=cypher.strip(),
            traversal_path=[],
            explanation="Node lookup returned zero matches."
        ).model_dump()

    traversal_path = []
    decisions = []
    past_issues = []
    requirements = []
    logics = []

    # 1. Decisions constraining this function
    for edge in db.memory_graph.edges:
        if edge["to"] == fn_node_id and edge["rel"] == Relationships.CONSTRAINS_FUNCTION:
            d_node = db.memory_graph.nodes.get(edge["from"])
            if d_node:
                decisions.append(d_node["properties"])
                traversal_path.append(TraversalStep(
                    from_node=f"Decision({d_node['properties'].get('adr_id')})",
                    relationship=Relationships.CONSTRAINS_FUNCTION,
                    to_node=f"Function({clean_name})",
                    explanation=f"Function '{clean_name}' is governed by Architectural Invariant in {d_node['properties'].get('adr_id')}"
                ))

    # 2. Issues that manifested in this function
    for edge in db.memory_graph.edges:
        if edge["to"] == fn_node_id and edge["rel"] == Relationships.MANIFESTED_IN_FUNCTION:
            iss_node = db.memory_graph.nodes.get(edge["from"])
            if iss_node:
                past_issues.append(iss_node["properties"])
                traversal_path.append(TraversalStep(
                    from_node=f"Issue({iss_node['properties'].get('ticket')})",
                    relationship=Relationships.MANIFESTED_IN_FUNCTION,
                    to_node=f"Function({clean_name})",
                    explanation=f"Function '{clean_name}' previously suffered from incident {iss_node['properties'].get('ticket')}"
                ))

    # 3. PRD Requirements
    for edge in db.memory_graph.edges:
        if edge["to"] == fn_node_id and edge["rel"] == Relationships.IMPLEMENTED_BY_FUNCTION:
            r_node = db.memory_graph.nodes.get(edge["from"])
            if r_node:
                requirements.append(r_node["properties"])
                traversal_path.append(TraversalStep(
                    from_node=f"FunctionalRequirement({edge['from'].replace('req:', '')})",
                    relationship=Relationships.IMPLEMENTED_BY_FUNCTION,
                    to_node=f"Function({clean_name})",
                    explanation=f"Function '{clean_name}' implements PRD requirement {edge['from'].replace('req:', '')}"
                ))

    # 4. Code Logic
    for edge in db.memory_graph.edges:
        if edge["from"] == fn_node_id and edge["rel"] == Relationships.EXECUTES_LOGIC:
            cl_node = db.memory_graph.nodes.get(edge["to"])
            if cl_node:
                logics.append(cl_node["properties"])

    is_safe = True
    warnings = []

    if decisions:
        is_safe = False
        for d in decisions:
            warnings.append(f"Architectural Invariant ({d.get('adr_id')}): {d.get('statement')}")

    if past_issues:
        is_safe = False
        tickets = ", ".join([iss.get("ticket") for iss in past_issues])
        warnings.append(f"Regression Risk: {len(past_issues)} past production incidents ({tickets}) manifested in this function.")

    safety_verdict = "⚠️ UNSAFE / STRICT CONSTRAINTS" if not is_safe else "✅ SAFE TO MODIFY"
    recommendation = (
        f"Verdict: {safety_verdict}\n"
        f"File: {fn_props.get('file_path')} (Lines {fn_props.get('line_start')}-{fn_props.get('line_end')})\n"
        f"Constraints Identified:\n" + "\n".join([f"  • {w}" for w in warnings])
        if warnings else "No blocking architectural decisions or past regression incidents recorded for this component."
    )

    return ExplainableResult(
        result={
            "function": clean_name,
            "file": fn_props.get("file_path"),
            "lines": f"{fn_props.get('line_start')}-{fn_props.get('line_end')}",
            "safe_to_modify": is_safe,
            "safety_verdict": safety_verdict,
            "governing_adrs": [d.get("adr_id") + ": " + d.get("title") for d in decisions],
            "past_issues": [iss.get("ticket") + ": " + iss.get("symptom") for iss in past_issues],
            "linked_prd_requirements": [r.get("title") for r in requirements],
            "executed_code_logics": [l.get("name") for l in logics],
            "warnings": warnings,
            "recommendation": recommendation
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Multi-hop safety audit: Function -> Decisions (ADR) + Issues (Operations) + Requirements (PRD)."
    ).model_dump()


def get_function_lineage(function_name: str) -> Dict[str, Any]:
    """
    Returns the complete evolutionary lineage across the 4-Pillar model:
    PRD Requirement -> ADR Architecture/Decision -> CodeBase Class/Logic -> Operations Issue/Fix -> ChangeTimeline (What & Why).
    """
    clean_name = function_name.replace("func:", "")
    audit = check_safe_to_change(clean_name)
    audit_data = audit.get("result", {})

    fn_node_id = f"func:{clean_name}"
    timeline_records = []
    traversal_path = audit.get("traversal_path", [])

    # Find timeline changes modifying this function or its logic
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "ChangeTimeline":
            props = node["properties"]
            # Check if linked to function or logic
            for edge in db.memory_graph.edges:
                if edge["from"] == nid and edge["rel"] == Relationships.CHANGED_NODE:
                    # check target
                    t_node = db.memory_graph.nodes.get(edge["to"], {})
                    if t_node.get("properties", {}).get("func_id") == fn_node_id or edge["to"] == fn_node_id:
                        timeline_records.append(props)
                        traversal_path.append(TraversalStep(
                            from_node=f"ChangeTimeline({props.get('commit_hash')[:7]})",
                            relationship=Relationships.CHANGED_NODE,
                            to_node=f"Function({clean_name})",
                            explanation=f"Commit on {props.get('date')} changed logic: '{props.get('what_changed')}' (Why: '{props.get('why_changed')}')"
                        ))

    timeline_records.sort(key=lambda x: x.get("date", ""), reverse=True)

    return ExplainableResult(
        result={
            "function": clean_name,
            "file": audit_data.get("file"),
            "lines": audit_data.get("lines"),
            "governing_adrs": audit_data.get("governing_adrs"),
            "linked_prd_requirements": audit_data.get("linked_prd_requirements"),
            "past_issues": audit_data.get("past_issues"),
            "timeline_history": timeline_records,
            "summary": f"Function '{clean_name}' links to {len(audit_data.get('linked_prd_requirements', []))} PRD requirements, {len(audit_data.get('governing_adrs', []))} ADR decisions, and has {len(timeline_records)} recorded timeline commits."
        },
        cypher_query="MATCH (r:FunctionalRequirement)-[:IMPLEMENTED_BY_FUNCTION]->(f:Function)<-[:CONSTRAINS_FUNCTION]-(d:Decision) ...",
        traversal_path=traversal_path,
        explanation="Full 4-pillar lineage audit with timeline history."
    ).model_dump()


def review_pr_diff(modified_functions: List[str], diff_summary: Optional[str] = None) -> Dict[str, Any]:
    """
    Reviews a proposed Pull Request by examining every modified function against the knowledge graph.
    Identifies if the PR touches code paths with known historical bug patterns or architectural constraints.
    """
    findings = []
    has_blocking_violations = False

    for fn_name in modified_functions:
        audit = check_safe_to_change(fn_name)
        audit_res = audit.get("result", {})
        if not audit_res.get("safe_to_modify", True):
            has_blocking_violations = True
            findings.append({
                "function": fn_name,
                "file": audit_res.get("file"),
                "status": "CONSTRAINED",
                "warnings": audit_res.get("warnings"),
                "adrs": audit_res.get("governing_adrs"),
                "past_issues": audit_res.get("past_issues")
            })
        else:
            findings.append({
                "function": fn_name,
                "status": "APPROVED",
                "warnings": []
            })

    verdict = "REQUEST_CHANGES: Architectural invariant violation or regression risk detected" if has_blocking_violations else "APPROVE: No graph constraints violated"

    return ExplainableResult(
        result={
            "pr_verdict": verdict,
            "blocking_risk": has_blocking_violations,
            "modified_function_audits": findings
        },
        cypher_query="MATCH (f:Function) WHERE f.name IN $modified_functions MATCH (f)<-[:CONSTRAINS_FUNCTION]-(d:Decision) ...",
        traversal_path=[],
        explanation="PR Review evaluation across 4-pillar graph."
    ).model_dump()


def cross_org_bug_check(symptom_pattern: str) -> Dict[str, Any]:
    """
    Searches past issues and incident RCAs across the organization by symptom pattern.
    """
    cypher = """
    MATCH (i:Issue)-[:ANALYZED_BY_RCA]->(rca:RCA)-[:RESOLVED_BY_FIX]->(fx:Fix)
    WHERE i.symptom CONTAINS $pattern OR rca.root_cause CONTAINS $pattern OR i.title CONTAINS $pattern
    RETURN i, rca, fx
    """

    matches = []
    pattern_lower = symptom_pattern.lower()
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Issue":
            props = node["properties"]
            rca_text = ""
            trigger_text = ""
            for edge in db.memory_graph.edges:
                if edge["from"] == nid and edge["rel"] == Relationships.ANALYZED_BY_RCA:
                    rca_node = db.memory_graph.nodes.get(edge["to"], {})
                    rca_text = rca_node.get("properties", {}).get("root_cause", "")
                    trigger_text = rca_node.get("properties", {}).get("trigger_condition", "")

            if (pattern_lower in props.get("symptom", "").lower() or 
                pattern_lower in props.get("title", "").lower() or 
                pattern_lower in rca_text.lower() or
                pattern_lower in trigger_text.lower()):
                matches.append({**props, "rca": rca_text, "trigger_condition": trigger_text})

    return ExplainableResult(
        result={
            "query_pattern": symptom_pattern,
            "found_matches_count": len(matches),
            "historical_issues": matches
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation="Cross-organizational issue search over Issue and RCA nodes."
    ).model_dump()
