"""
Developer Agent MCP Tools.
Designed for Software Engineers: outputs detailed technical root causes, file paths, line numbers,
ADR constraints, and code-level remediation steps.
"""

from typing import Dict, Any, List, Optional
from ..db import db
from ..schema import ExplainableResult, TraversalStep, Relationships


def debug_issue(error_logs: str) -> Dict[str, Any]:
    """
    Analyzes application error logs or incident symptoms (e.g., 'REFUND_TIMEOUT', 'FRAUD_SERVICE_UNAVAILABLE').
    Matches symptoms against knowledge graph BugFixes and Runbooks, returning the Root Cause Analysis (RCA),
    historical ticket ID, affected code files, line numbers, and verified resolution steps.
    """
    cypher = """
    MATCH (b:BugFix)
    WHERE b.symptom CONTAINS $error OR b.description CONTAINS $error OR b.rca CONTAINS $error
    OPTIONAL MATCH (rb:Runbook)-[:RESOLVES_BUG]->(b)
    OPTIONAL MATCH (b)-[:FIXED_IN]->(f:Function)
    OPTIONAL MATCH (b)-[:FIXED_BY]->(cr:ChangeRecord)
    RETURN b, rb, f, cr
    """

    error_lower = error_logs.lower()
    matches = []
    traversal_path = []

    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "BugFix":
            props = node["properties"]
            symptom = props.get("symptom", "").lower()
            desc = props.get("description", "").lower()
            rca = props.get("rca", "").lower()
            ticket = props.get("ticket", nid)

            # Match symptoms or error keywords
            error_keywords = [w for w in error_lower.replace("_", " ").split() if len(w) > 3]
            matched = any(k in symptom or k in desc or k in rca for k in error_keywords) or (ticket.lower() in error_lower)

            if matched:
                # Find associated function
                target_funcs = []
                for edge in db.memory_graph.edges:
                    if edge["from"] == nid and edge["rel"] == Relationships.FIXED_IN:
                        fn_node = db.memory_graph.nodes.get(edge["to"])
                        if fn_node:
                            target_funcs.append(fn_node["properties"])
                            traversal_path.append(TraversalStep(
                                from_node=f"BugFix({ticket})",
                                relationship=Relationships.FIXED_IN,
                                to_node=f"Function({fn_node['properties'].get('name')})",
                                explanation=f"Incident {ticket} directly impacted function '{fn_node['properties'].get('name')}'"
                            ))

                # Find associated runbook procedure
                runbook_steps = None
                for edge in db.memory_graph.edges:
                    if edge["to"] == nid and edge["rel"] == Relationships.RESOLVES_BUG:
                        rb_node = db.memory_graph.nodes.get(edge["from"])
                        if rb_node:
                            runbook_steps = rb_node["properties"].get("resolution_steps")
                            traversal_path.append(TraversalStep(
                                from_node=f"Runbook({edge['from']})",
                                relationship=Relationships.RESOLVES_BUG,
                                to_node=f"BugFix({ticket})",
                                explanation=f"Runbook procedure '{edge['from']}' documents official resolution for {ticket}"
                            ))

                matches.append({
                    "ticket_id": ticket,
                    "symptom": props.get("symptom"),
                    "root_cause_analysis": props.get("rca"),
                    "fix_summary": props.get("fix_summary"),
                    "runbook_resolution_steps": runbook_steps or props.get("fix_summary"),
                    "affected_code_locations": [
                        {
                            "function": f.get("name"),
                            "file": f.get("file_path"),
                            "lines": f"{f.get('line_start')}-{f.get('line_end')}"
                        } for f in target_funcs
                    ]
                })

    if not matches:
        summary = f"No direct historical BugFix match found in knowledge graph for '{error_logs}'. Search runbooks or initiate new RCA."
    else:
        top = matches[0]
        code_loc = top["affected_code_locations"][0] if top["affected_code_locations"] else {"file": "unknown", "lines": "unknown"}
        summary = (
            f"🚨 Match Identified: {top['ticket_id']} ({top['symptom']})\n"
            f"• Root Cause Analysis (RCA): {top['root_cause_analysis']}\n"
            f"• Target Code: {code_loc.get('file')} (lines {code_loc.get('lines')})\n"
            f"• Resolution: {top['runbook_resolution_steps']}"
        )

    return ExplainableResult(
        result={
            "matched_incidents": matches,
            "technical_diagnostic_summary": summary
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Graph traversal: Incident Logs -> BugFix -> Function & Runbook resolution procedure."
    ).model_dump()


def check_safe_to_change(function_name: str, proposed_change: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluates whether it is safe for an engineer or coding agent to modify or override a specific function.
    Cross-references architectural ADR constraints, past regression bugs, and PRD dependencies.
    """
    cypher = """
    MATCH (f:Function {name: $function_name})
    OPTIONAL MATCH (dec:Decision)-[:AFFECTS]->(f)
    OPTIONAL MATCH (adr:ADR)-[:DOCUMENTS_DECISION]->(dec)
    OPTIONAL MATCH (b:BugFix)-[:FIXED_IN]->(f)
    OPTIONAL MATCH (r:Requirement)-[:IMPLEMENTED_BY]->(f)
    RETURN f, collect(DISTINCT adr) AS adrs, collect(DISTINCT dec) AS decisions,
           collect(DISTINCT b) AS past_bugs, collect(DISTINCT r) AS prd_requirements
    """

    fn_node_id = None
    fn_props = None
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Function" and node["properties"].get("name") == function_name:
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
    adrs = []
    decisions = []
    past_bugs = []
    requirements = []

    # 1. Inspect Decisions / ADRs affecting this function
    for edge in db.memory_graph.edges:
        if edge["to"] == fn_node_id and edge["rel"] == Relationships.AFFECTS:
            dec_node = db.memory_graph.nodes.get(edge["from"])
            if dec_node:
                decisions.append(dec_node["properties"])
                adr_id = dec_node["properties"].get("adr_id")
                adr_node = db.memory_graph.nodes.get(adr_id)
                if adr_node:
                    adrs.append(adr_node["properties"])
                traversal_path.append(TraversalStep(
                    from_node=f"Decision({dec_node['properties'].get('id')})",
                    relationship=Relationships.AFFECTS,
                    to_node=f"Function({function_name})",
                    explanation=f"Function '{function_name}' is constrained by Architectural Decision {adr_id}"
                ))

    # 2. Inspect Past Bug Fixes
    for edge in db.memory_graph.edges:
        if edge["to"] == fn_node_id and edge["rel"] == Relationships.FIXED_IN:
            bug_node = db.memory_graph.nodes.get(edge["from"])
            if bug_node:
                past_bugs.append(bug_node["properties"])
                traversal_path.append(TraversalStep(
                    from_node=f"BugFix({edge['from']})",
                    relationship=Relationships.FIXED_IN,
                    to_node=f"Function({function_name})",
                    explanation=f"Function '{function_name}' was previously modified to resolve incident {edge['from']}"
                ))

    # 3. Inspect PRD Requirements
    for edge in db.memory_graph.edges:
        if edge["to"] == fn_node_id and edge["rel"] == Relationships.IMPLEMENTED_BY:
            req_node = db.memory_graph.nodes.get(edge["from"])
            if req_node:
                requirements.append(req_node["properties"])
                traversal_path.append(TraversalStep(
                    from_node=f"Requirement({edge['from']})",
                    relationship=Relationships.IMPLEMENTED_BY,
                    to_node=f"Function({function_name})",
                    explanation=f"Function '{function_name}' implements business requirement {edge['from']}"
                ))

    # Assess safety
    is_safe = True
    warnings = []

    if decisions:
        is_safe = False
        for d in decisions:
            warnings.append(f"Architectural Constraint ({d.get('adr_id')}): {d.get('statement')}")

    if past_bugs:
        is_safe = False
        bug_list = ", ".join([b.get("id") for b in past_bugs])
        warnings.append(f"Regression Risk: {len(past_bugs)} past production bugs ({bug_list}) were caused by changes to this function.")

    safety_verdict = "⚠️ UNSAFE / STRICT CONSTRAINTS" if not is_safe else "✅ SAFE TO MODIFY"
    recommendation = (
        f"Verdict: {safety_verdict}\n"
        f"File: {fn_props.get('file_path')} (Lines {fn_props.get('line_start')}-{fn_props.get('line_end')})\n"
        f"Constraints Identified:\n" + "\n".join([f"  • {w}" for w in warnings])
        if warnings else "No blocking architectural decisions or regression bugs recorded for this component."
    )

    return ExplainableResult(
        result={
            "function": function_name,
            "file": fn_props.get("file_path"),
            "lines": f"{fn_props.get('line_start')}-{fn_props.get('line_end')}",
            "safe_to_modify": is_safe,
            "safety_verdict": safety_verdict,
            "governing_adrs": [a.get("id") + ": " + a.get("title") for a in adrs],
            "past_bug_fixes": [b.get("id") + ": " + b.get("symptom") for b in past_bugs],
            "linked_prd_requirements": [r.get("id") + ": " + r.get("title") for r in requirements],
            "warnings": warnings,
            "recommendation": recommendation
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Multi-hop safety audit: Function -> Decisions (ADR) + BugFixes + PRD Requirements."
    ).model_dump()


def get_function_lineage(function_name: str) -> Dict[str, Any]:
    """
    Returns the complete evolutionary lineage of a function:
    why it was originally introduced, which PRD requirements it serves, which ADRs govern it,
    and every historical commit and bugfix that altered it.
    """
    cypher = """
    MATCH (f:Function {name: $function_name})
    OPTIONAL MATCH (f)-[:CHANGED_BY]->(cr:ChangeRecord)
    OPTIONAL MATCH (r:Requirement)-[:IMPLEMENTED_BY]->(f)
    OPTIONAL MATCH (dec:Decision)-[:AFFECTS]->(f)
    RETURN f, collect(cr) AS commits, collect(r) AS requirements, collect(dec) AS decisions
    """

    fn_node_id = None
    fn_props = None
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "Function" and node["properties"].get("name") == function_name:
            fn_node_id = nid
            fn_props = node["properties"]
            break

    if not fn_node_id:
        return ExplainableResult(
            result={"error": f"Function '{function_name}' not found"},
            cypher_query=cypher.strip(),
            traversal_path=[],
            explanation="Lookup returned no node."
        ).model_dump()

    commits = []
    requirements = []
    decisions = []
    traversal_path = []

    for edge in db.memory_graph.edges:
        if edge["from"] == fn_node_id and edge["rel"] == Relationships.CHANGED_BY:
            c_node = db.memory_graph.nodes.get(edge["to"])
            if c_node:
                commits.append(c_node["properties"])
        elif edge["to"] == fn_node_id and edge["rel"] == Relationships.IMPLEMENTED_BY:
            r_node = db.memory_graph.nodes.get(edge["from"])
            if r_node:
                requirements.append(r_node["properties"])
        elif edge["to"] == fn_node_id and edge["rel"] == Relationships.AFFECTS:
            d_node = db.memory_graph.nodes.get(edge["from"])
            if d_node:
                decisions.append(d_node["properties"])

    commits.sort(key=lambda x: x.get("date", ""), reverse=True)

    return ExplainableResult(
        result={
            "function": function_name,
            "signature": fn_props.get("signature"),
            "file": fn_props.get("file_path"),
            "line_numbers": f"{fn_props.get('line_start')}-{fn_props.get('line_end')}",
            "prd_requirements_fulfilled": requirements,
            "architectural_decisions_applied": decisions,
            "commit_change_history": commits,
            "summary": f"Function '{function_name}' has {len(commits)} commits, serves {len(requirements)} PRD requirements, and is governed by {len(decisions)} architectural decisions."
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation="Full history and reason lineage traversal."
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
                "past_bugs": audit_res.get("past_bug_fixes")
            })
        else:
            findings.append({
                "function": fn_name,
                "status": "APPROVED",
                "warnings": []
            })

    verdict = "REQUEST_CHANGES: Architectural or regression risk detected" if has_blocking_violations else "APPROVE: No graph constraints violated"

    return ExplainableResult(
        result={
            "pr_verdict": verdict,
            "blocking_risk": has_blocking_violations,
            "modified_function_audits": findings
        },
        cypher_query="MATCH (f:Function) WHERE f.name IN $modified_functions MATCH (f)<-[:AFFECTS]-(d:Decision) ...",
        traversal_path=[],
        explanation="PR Review graph evaluation across all touched functions."
    ).model_dump()


def cross_org_bug_check(symptom_pattern: str) -> Dict[str, Any]:
    """
    Searches past bugs and incident RCAs across applications in the organization to see if a similar issue
    was ever encountered elsewhere.
    """
    cypher = """
    MATCH (b:BugFix)
    WHERE b.symptom CONTAINS $pattern OR b.rca CONTAINS $pattern OR b.description CONTAINS $pattern
    RETURN b
    """

    matches = []
    pattern_lower = symptom_pattern.lower()
    for nid, node in db.memory_graph.nodes.items():
        if node["label"] == "BugFix":
            props = node["properties"]
            if pattern_lower in props.get("symptom", "").lower() or pattern_lower in props.get("rca", "").lower():
                matches.append(props)

    return ExplainableResult(
        result={
            "query_pattern": symptom_pattern,
            "found_matches_count": len(matches),
            "historical_incidents": matches
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation="Cross-organizational incident search over graph BugFix nodes."
    ).model_dump()
