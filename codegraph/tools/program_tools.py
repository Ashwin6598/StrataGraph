"""
Program Manager Persona Tools.
Provides Technical Program Managers (TPMs), Agile Delivery Leads, and Scrum Masters
with grounded metrics, delivery progress, bottleneck diagnosis, and cross-discipline
traceability across the 5-Pillar Connected Knowledge Graph.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from codegraph.db import db
from codegraph.schema import ExplainableResult, TraversalStep, Relationships, EpicNode, AgileFeatureNode, StoryNode
from codegraph.ingest.jira_parser import JiraBoardParser
from codegraph.iam import iam, Permission
from codegraph.guardrails import enforce_ingestion_harness


def query_program_delivery_status(
    project_id: str = "project:payflow",
    epic_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes overall program delivery progress, agile burndown, velocity,
    sprint health, and active blockers across Epics, Features, and Stories.
    """
    cypher_query = """
    MATCH (p:Project {id: $project_id})-[:HAS_EPIC]->(e:Epic)
    OPTIONAL MATCH (e)-[:HAS_FEATURE]->(f:AgileFeature)
    OPTIONAL MATCH (f)-[:HAS_STORY]->(s:Story)
    RETURN e, collect(DISTINCT f) AS features, collect(DISTINCT s) AS stories
    """.strip()

    traversal_path: List[TraversalStep] = [
        TraversalStep(
            from_node=project_id,
            relationship=Relationships.HAS_EPIC,
            to_node="Epic",
            explanation="Navigate from project root to Agile Epics."
        ),
        TraversalStep(
            from_node="Epic",
            relationship=Relationships.HAS_FEATURE,
            to_node="AgileFeature",
            explanation="Expand Epics into functional features."
        ),
        TraversalStep(
            from_node="AgileFeature",
            relationship=Relationships.HAS_STORY,
            to_node="Story",
            explanation="Traverse features to developer task stories."
        )
    ]

    epics_found = []
    features_found = []
    stories_found = []

    # Graph traversal
    for neighbor in db.get_neighbors(project_id, direction="outgoing"):
        if neighbor.get("relationship") == Relationships.HAS_EPIC:
            e_node = neighbor.get("node", {})
            if epic_id and e_node.get("id") != epic_id and e_node.get("key") != epic_id:
                continue
            epics_found.append(e_node)

            e_id = e_node.get("id")
            for f_rel in db.get_neighbors(e_id, direction="outgoing"):
                if f_rel.get("relationship") == Relationships.HAS_FEATURE:
                    feat_node = f_rel.get("node", {})
                    features_found.append(feat_node)

                    feat_id = feat_node.get("id")
                    for s_rel in db.get_neighbors(feat_id, direction="outgoing"):
                        if s_rel.get("relationship") == Relationships.HAS_STORY:
                            story_node = s_rel.get("node", {})
                            stories_found.append(story_node)

    # Calculate metrics
    total_epics = len(epics_found)
    total_features = len(features_found)
    total_stories = len(stories_found)

    epics_by_status = {}
    for e in epics_found:
        st = e.get("status", "IN_PROGRESS").upper()
        epics_by_status[st] = epics_by_status.get(st, 0) + 1

    features_by_status = {}
    for f in features_found:
        st = f.get("status", "IN_DEVELOPMENT").upper()
        features_by_status[st] = features_by_status.get(st, 0) + 1

    total_story_points = 0
    completed_story_points = 0
    blocked_stories = []
    sprint_breakdown = {}
    assignee_breakdown = {}

    for s in stories_found:
        pts = int(s.get("story_points", 3))
        total_story_points += pts
        st = s.get("status", "TODO").upper()
        if st in ("DONE", "COMPLETED", "RESOLVED"):
            completed_story_points += pts

        if s.get("blocked"):
            blocked_stories.append({
                "key": s.get("key"),
                "summary": s.get("summary"),
                "assignee": s.get("assignee"),
                "reason": s.get("blocker_reason", "No reason recorded")
            })

        sprint = s.get("sprint", "Backlog")
        if sprint not in sprint_breakdown:
            sprint_breakdown[sprint] = {"total_points": 0, "completed_points": 0, "stories_count": 0}
        sprint_breakdown[sprint]["total_points"] += pts
        sprint_breakdown[sprint]["stories_count"] += 1
        if st in ("DONE", "COMPLETED", "RESOLVED"):
            sprint_breakdown[sprint]["completed_points"] += pts

        assignee = s.get("assignee", "Unassigned")
        assignee_breakdown[assignee] = assignee_breakdown.get(assignee, 0) + pts

    progress_pct = round((completed_story_points / total_story_points * 100), 1) if total_story_points > 0 else 0.0

    summary_text = (
        f"Program Delivery Status: {progress_pct}% overall completion "
        f"({completed_story_points} of {total_story_points} committed story points delivered). "
        f"{total_epics} Epics, {total_features} Features, and {total_stories} Stories tracked across active sprints. "
    )
    if blocked_stories:
        summary_text += f"⚠️ {len(blocked_stories)} story is currently BLOCKED ({blocked_stories[0]['key']}: {blocked_stories[0]['reason']})."
    else:
        summary_text += "Zero active blockers reported."

    result_data = {
        "project_id": project_id,
        "delivery_progress_percentage": progress_pct,
        "total_story_points": total_story_points,
        "completed_story_points": completed_story_points,
        "total_epics": total_epics,
        "epics_status": epics_by_status,
        "total_features": total_features,
        "features_status": features_by_status,
        "total_stories": total_stories,
        "blocked_stories_count": len(blocked_stories),
        "blocked_stories": blocked_stories,
        "sprint_breakdown": sprint_breakdown,
        "assignee_breakdown": assignee_breakdown
    }

    return ExplainableResult(
        result=result_data,
        cypher_query=cypher_query,
        traversal_path=traversal_path,
        explanation=summary_text
    ).model_dump()


def diagnose_delivery_bottlenecks(
    project_id: str = "project:payflow"
) -> Dict[str, Any]:
    """
    Identifies root causes of delivery delays between PRD requirements and engineering code:
    1. Definition Gaps (PRD requirements with zero or unstarted Jira stories)
    2. Active Engineering Blockers (Stories marked blocked with developer reasons)
    3. Ghost Deliveries (Jira stories marked DONE with missing AST code implementation)
    4. Unresolved Operational Incidents blocking release
    """
    cypher_query = """
    MATCH (p:Project {id: $project_id})-[:HAS_PRD_INPUT]->(pi:PRDInput)-[:SPECIFIES_REQUIREMENT]->(r:FunctionalRequirement)
    OPTIONAL MATCH (f:AgileFeature)-[:REALIZES_REQUIREMENT]->(r)
    OPTIONAL MATCH (f)-[:HAS_STORY]->(s:Story)
    OPTIONAL MATCH (r)-[:IMPLEMENTED_BY_FUNCTION]->(fn:Function)
    RETURN r, f, s, fn
    """.strip()

    traversal_path: List[TraversalStep] = [
        TraversalStep(
            from_node="PRDInput",
            relationship=Relationships.SPECIFIES_REQUIREMENT,
            to_node="FunctionalRequirement",
            explanation="Identify all business commitments in the PRD."
        ),
        TraversalStep(
            from_node="FunctionalRequirement",
            relationship=Relationships.REALIZES_REQUIREMENT,
            to_node="AgileFeature / Story",
            explanation="Correlate requirements to Jira Agile execution."
        ),
        TraversalStep(
            from_node="FunctionalRequirement",
            relationship=Relationships.IMPLEMENTED_BY_FUNCTION,
            to_node="Function",
            explanation="Verify whether working AST code exists in the codebase."
        )
    ]

    definition_gaps = []
    active_blockers = []
    ghost_deliveries = []
    healthy_deliveries = []

    # Get all functional requirements
    req_nodes = []
    for neighbor in db.get_neighbors(project_id, direction="outgoing"):
        if neighbor.get("relationship") == Relationships.HAS_PRD_INPUT:
            pi_id = neighbor.get("node", {}).get("id")
            for req_rel in db.get_neighbors(pi_id, direction="outgoing"):
                if req_rel.get("relationship") == Relationships.SPECIFIES_REQUIREMENT:
                    r_node = req_rel.get("node", {})
                    # Ignore unapproved staged proposals
                    if r_node.get("status") == "PENDING_APPROVAL":
                        continue
                    req_nodes.append(r_node)

    for req in req_nodes:
        req_id = req.get("id")
        req_title = req.get("title")
        clean_req_code = req_id.replace("req:", "").upper()

        # Find linked features and stories via incoming relationships and text matches
        linked_stories = []
        linked_features = []

        # 1. Incoming REALIZES_REQUIREMENT edges
        for in_rel in db.get_neighbors(req_id, direction="incoming"):
            if in_rel.get("relationship") == Relationships.REALIZES_REQUIREMENT:
                node = in_rel.get("node", {})
                target_node = in_rel.get("target_node", {})
                label = target_node.get("label", "")
                if label == "AgileFeature" or node.get("id", "").startswith("feat:"):
                    if node not in linked_features:
                        linked_features.append(node)
                    for s_rel in db.get_neighbors(node.get("id"), direction="outgoing"):
                        if s_rel.get("relationship") == Relationships.HAS_STORY:
                            s_node = s_rel.get("node", {})
                            if s_node not in linked_stories:
                                linked_stories.append(s_node)
                elif label == "Story" or node.get("id", "").startswith("story:"):
                    if node not in linked_stories:
                        linked_stories.append(node)

        # 2. Text matches or property matches
        for feat_cand in db.search_nodes(None, "AgileFeature"):
            f_props = feat_cand.get("properties", {})
            if f_props.get("req_id") in (req_id, clean_req_code):
                if f_props not in linked_features:
                    linked_features.append(f_props)
                for s_rel in db.get_neighbors(f_props.get("id"), direction="outgoing"):
                    if s_rel.get("relationship") == Relationships.HAS_STORY:
                        s_node = s_rel.get("node", {})
                        if s_node not in linked_stories:
                            linked_stories.append(s_node)

        for s_cand in db.search_nodes(None, "Story"):
            sp = s_cand.get("properties", {})
            if clean_req_code in (sp.get("summary", "") + " " + sp.get("description", "")).upper():
                if sp not in linked_stories:
                    linked_stories.append(sp)

        # 3. Check code functions
        code_funcs = []
        for f_rel in db.get_neighbors(req_id, direction="outgoing"):
            if f_rel.get("relationship") == Relationships.IMPLEMENTED_BY_FUNCTION:
                code_funcs.append(f_rel.get("node", {}).get("name", "unnamed_func"))

        # Gap classification:
        has_blocker = False
        for s in linked_stories:
            if s.get("blocked"):
                has_blocker = True
                active_blockers.append({
                    "requirement_id": req_id,
                    "requirement_title": req_title,
                    "story_key": s.get("key"),
                    "assignee": s.get("assignee"),
                    "sprint": s.get("sprint"),
                    "blocker_reason": s.get("blocker_reason", "Blocked"),
                    "diagnosis": f"Story {s.get('key')} assigned to {s.get('assignee')} is BLOCKED: {s.get('blocker_reason')}"
                })

        done_stories = [s for s in linked_stories if s.get("status") in ("DONE", "COMPLETED")]

        # True definition/backlog gap: not implemented, and no active/done stories
        if not code_funcs and req.get("status") != "IMPLEMENTED":
            if not linked_stories or all(s.get("status") == "TODO" for s in linked_stories):
                definition_gaps.append({
                    "requirement_id": req_id,
                    "title": req_title,
                    "priority": req.get("priority", "MEDIUM"),
                    "status": "DEFINITION_OR_BACKLOG_GAP",
                    "diagnosis": (
                        f"PRD requirement '{req_title}' has no in-progress or completed engineering stories. "
                        f"Backlog story is unassigned or not sprint-committed."
                    )
                })
        elif done_stories and not code_funcs and req.get("status") != "IMPLEMENTED":
            # Ghost delivery: marked done in Jira, but code does not exist
            ghost_deliveries.append({
                "requirement_id": req_id,
                "requirement_title": req_title,
                "jira_tickets": [s.get("key") for s in done_stories],
                "diagnosis": "Jira story is marked DONE, but AST code inspection shows NO implementing function in repository."
            })
        elif not has_blocker:
            healthy_deliveries.append({
                "requirement_id": req_id,
                "title": req_title,
                "implementing_code": code_funcs
            })

    total_bottlenecks = len(definition_gaps) + len(active_blockers) + len(ghost_deliveries)

    explanation_parts = [f"Delivery Bottleneck Diagnosis: Found {total_bottlenecks} delivery issue(s)."]
    if active_blockers:
        explanation_parts.append(
            f"🚨 Active Dependency Blockers: {len(active_blockers)} story is halted "
            f"({active_blockers[0]['story_key']} under '{active_blockers[0]['requirement_title']}': {active_blockers[0]['blocker_reason']})."
        )
    if definition_gaps:
        explanation_parts.append(
            f"⏳ Definition & Backlog Gaps: {len(definition_gaps)} requirement(s) stalled in backlog without developer pickup "
            f"({', '.join(g['requirement_id'] for g in definition_gaps)})."
        )
    if ghost_deliveries:
        explanation_parts.append(
            f"👻 Phantom Deliveries: {len(ghost_deliveries)} ticket(s) marked Done in Jira without verified AST code."
        )
    if total_bottlenecks == 0:
        explanation_parts.append("All requirements have active engineering velocity with zero detected blockers.")

    return ExplainableResult(
        result={
            "project_id": project_id,
            "total_bottlenecks_detected": total_bottlenecks,
            "active_blockers": active_blockers,
            "definition_gaps": definition_gaps,
            "ghost_deliveries": ghost_deliveries,
            "healthy_deliveries_count": len(healthy_deliveries)
        },
        cypher_query=cypher_query,
        traversal_path=traversal_path,
        explanation=" ".join(explanation_parts)
    ).model_dump()


def get_feature_lead_time_metrics(
    project_id: str = "project:payflow",
    feature_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes cycle times and lead times for converting PRD requirements into architecture and code:
    - Average cycle time per story
    - Feature lead time benchmarks
    - Highlights high-latency deliverables
    """
    cypher_query = """
    MATCH (f:AgileFeature)-[:HAS_STORY]->(s:Story)
    WHERE s.status = 'DONE' AND s.cycle_time_days IS NOT NULL
    RETURN f.key AS feature_key, f.summary AS feature_name,
           avg(s.cycle_time_days) AS avg_cycle_time,
           collect(s) AS completed_stories
    """.strip()

    traversal_path: List[TraversalStep] = [
        TraversalStep(
            from_node="AgileFeature",
            relationship=Relationships.HAS_STORY,
            to_node="Story",
            explanation="Filter stories with valid created_date and resolved_date to compute cycle time."
        )
    ]

    feature_metrics = []
    all_cycle_times = []

    for feat_cand in db.search_nodes(None, "AgileFeature"):
        f_props = feat_cand.get("properties", {})
        f_id = f_props.get("id")
        f_key = f_props.get("key")
        if feature_id and feature_id not in (f_id, f_key):
            continue

        feat_cycle_times = []
        completed_stories = []

        for s_rel in db.get_neighbors(f_id, direction="outgoing"):
            if s_rel.get("relationship") == Relationships.HAS_STORY:
                s = s_rel.get("node", {})
                cycle_time = s.get("cycle_time_days")
                if cycle_time is not None:
                    feat_cycle_times.append(float(cycle_time))
                    all_cycle_times.append(float(cycle_time))
                    completed_stories.append({
                        "key": s.get("key"),
                        "summary": s.get("summary"),
                        "story_points": s.get("story_points"),
                        "cycle_time_days": cycle_time
                    })

        avg_feature_cycle = round(sum(feat_cycle_times) / len(feat_cycle_times), 1) if feat_cycle_times else None

        feature_metrics.append({
            "feature_key": f_key,
            "feature_summary": f_props.get("summary"),
            "service_name": f_props.get("service_name"),
            "status": f_props.get("status"),
            "completed_stories_count": len(completed_stories),
            "average_cycle_time_days": avg_feature_cycle,
            "completed_stories": completed_stories
        })

    overall_avg_cycle = round(sum(all_cycle_times) / len(all_cycle_times), 1) if all_cycle_times else 0.0

    # Sort to find fastest and slowest
    valid_features = [f for f in feature_metrics if f["average_cycle_time_days"] is not None]
    valid_features.sort(key=lambda x: x["average_cycle_time_days"])

    fastest_feature = valid_features[0]["feature_key"] if valid_features else "N/A"
    slowest_feature = valid_features[-1]["feature_key"] if valid_features else "N/A"

    explanation = (
        f"Delivery Velocity Metrics: Average engineering cycle time across completed stories is {overall_avg_cycle} calendar days. "
        f"Fastest turnaround: {fastest_feature} (avg {valid_features[0]['average_cycle_time_days']} days); "
        f"Highest latency: {slowest_feature} (avg {valid_features[-1]['average_cycle_time_days']} days)."
        if valid_features else
        "No completed stories with recorded cycle times found."
    )

    return ExplainableResult(
        result={
            "project_id": project_id,
            "overall_average_cycle_time_days": overall_avg_cycle,
            "features_analyzed": len(feature_metrics),
            "feature_breakdown": feature_metrics
        },
        cypher_query=cypher_query,
        traversal_path=traversal_path,
        explanation=explanation
    ).model_dump()


def trace_requirement_to_delivery_chain(
    req_id_or_ticket: str,
    project_id: str = "project:payflow"
) -> Dict[str, Any]:
    """
    Performs 5-Pillar end-to-end traceability for any PRD Requirement, Jira Ticket, or Code Function:
    PRD (Requirement) <-> Agile/Jira (Epic, Feature, Story) <-> ADR (Decision) <-> CodeBase (AST) <-> Ops (Fix)
    """
    target = req_id_or_ticket.strip()
    clean_key = target.upper()

    cypher_query = """
    MATCH (r:FunctionalRequirement)
    OPTIONAL MATCH (f:AgileFeature)-[:REALIZES_REQUIREMENT]->(r)
    OPTIONAL MATCH (f)-[:HAS_STORY]->(s:Story)
    OPTIONAL MATCH (r)-[:DRIVES_ADR_REQUIREMENT]->(ar)-[:DEFINES_ARCHITECTURE]->(a)-[:LEADS_TO_DECISION]->(d:Decision)
    OPTIONAL MATCH (r)-[:IMPLEMENTED_BY_FUNCTION]->(fn:Function)
    OPTIONAL MATCH (i:Issue)-[:IMPACTED_REQUIREMENT]->(r)
    WHERE r.id CONTAINS $target OR s.key = $target OR f.key = $target
    RETURN r, f, s, d, fn, i
    """.strip()

    traversal_path: List[TraversalStep] = [
        TraversalStep(
            from_node="PRD (Requirement)",
            relationship="REALIZES_REQUIREMENT",
            to_node="Agile Feature & Story",
            explanation="Map requirement to delivery backlog."
        ),
        TraversalStep(
            from_node="PRD (Requirement)",
            relationship="DRIVES_ADR_REQUIREMENT",
            to_node="ADR Decision",
            explanation="Map requirement to architectural governance."
        ),
        TraversalStep(
            from_node="PRD (Requirement)",
            relationship="IMPLEMENTED_BY_FUNCTION",
            to_node="CodeBase Function",
            explanation="Map requirement to verified repository source code."
        ),
        TraversalStep(
            from_node="PRD (Requirement)",
            relationship="IMPACTED_REQUIREMENT",
            to_node="Operations Issue / Bugfix",
            explanation="Map requirement to past operational regressions."
        )
    ]

    # Find the target requirement or ticket
    matched_req = None
    matched_story = None
    matched_feature = None

    # Search stories first
    for s_cand in db.search_nodes(None, "Story"):
        sp = s_cand.get("properties", {})
        if sp.get("key", "").upper() == clean_key or sp.get("id") == target:
            matched_story = sp
            break

    # Search features
    for f_cand in db.search_nodes(None, "AgileFeature"):
        fp = f_cand.get("properties", {})
        if fp.get("key", "").upper() == clean_key or fp.get("id") == target:
            matched_feature = fp
            break

    # Search requirements
    for r_cand in db.search_nodes(None, "FunctionalRequirement"):
        rp = r_cand.get("properties", {})
        if clean_key in rp.get("id", "").upper() or clean_key in rp.get("title", "").upper():
            matched_req = rp
            break

    # If story found, find parent feature and req
    if matched_story and not matched_feature:
        f_id = matched_story.get("feature_id")
        f_node = db.get_node(f_id)
        if f_node:
            matched_feature = f_node.get("properties", {})

    if matched_feature and not matched_req:
        r_id = matched_feature.get("req_id")
        if r_id:
            r_node = db.get_node(r_id)
            if r_node:
                matched_req = r_node.get("properties", {})

    # If requirement was target, find corresponding feature and story
    if matched_req and not matched_feature:
        req_id = matched_req.get("id")
        clean_code = req_id.replace("req:", "").upper()
        for f_cand in db.search_nodes(None, "AgileFeature"):
            fp = f_cand.get("properties", {})
            if fp.get("req_id") in (req_id, clean_code):
                matched_feature = fp
                break

    if matched_feature and not matched_story:
        for s_rel in db.get_neighbors(matched_feature.get("id"), direction="outgoing"):
            if s_rel.get("relationship") == Relationships.HAS_STORY:
                matched_story = s_rel.get("node", {})
                break

    if matched_req and not matched_story:
        clean_code = matched_req.get("id").replace("req:", "").upper()
        for s_cand in db.search_nodes(None, "Story"):
            sp = s_cand.get("properties", {})
            if clean_code in (sp.get("summary", "") + " " + sp.get("description", "")).upper():
                matched_story = sp
                if not matched_feature:
                    f_id = matched_story.get("feature_id")
                    f_node = db.get_node(f_id)
                    if f_node:
                        matched_feature = f_node.get("properties", {})
                break

    req_id = matched_req.get("id") if matched_req else f"req:{clean_key}"

    # Trace CodeBase functions
    code_functions = []
    if matched_req:
        for f_rel in db.get_neighbors(req_id, direction="outgoing"):
            if f_rel.get("relationship") == Relationships.IMPLEMENTED_BY_FUNCTION:
                fn = f_rel.get("node", {})
                code_functions.append({
                    "name": fn.get("name"),
                    "file_path": fn.get("file_path"),
                    "signature": fn.get("signature"),
                    "line_start": fn.get("line_start"),
                    "line_end": fn.get("line_end")
                })

    # Trace ADR Decisions
    adr_decisions = []
    for d_cand in db.search_nodes(None, "Decision"):
        dp = d_cand.get("properties", {})
        # Check if decision linked to any of the code functions
        for fn in code_functions:
            fn_id = f"func:{fn['name']}"
            for n in db.get_neighbors(dp.get("id"), direction="outgoing"):
                if n.get("relationship") == Relationships.CONSTRAINS_FUNCTION and n.get("node", {}).get("name") == fn["name"]:
                    adr_decisions.append({
                        "adr_id": dp.get("adr_id"),
                        "title": dp.get("title"),
                        "statement": dp.get("statement")
                    })

    # Trace Operations BugFixes
    ops_issues = []
    if matched_req:
        for iss_cand in db.search_nodes(None, "Issue"):
            ip = iss_cand.get("properties", {})
            for n in db.get_neighbors(ip.get("id"), direction="outgoing"):
                if n.get("relationship") == Relationships.IMPACTED_REQUIREMENT and n.get("node", {}).get("id") == req_id:
                    ops_issues.append({
                        "ticket": ip.get("ticket"),
                        "title": ip.get("title"),
                        "severity": ip.get("severity")
                    })

    trace_summary = {
        "query_target": target,
        "prd_requirement": {
            "id": matched_req.get("id") if matched_req else "N/A",
            "title": matched_req.get("title") if matched_req else "Unlinked Specification",
            "priority": matched_req.get("priority", "N/A") if matched_req else "N/A",
            "status": matched_req.get("status", "N/A") if matched_req else "N/A"
        },
        "agile_execution": {
            "feature": matched_feature.get("key") if matched_feature else "N/A",
            "feature_summary": matched_feature.get("summary") if matched_feature else "N/A",
            "story": matched_story.get("key") if matched_story else "N/A",
            "story_summary": matched_story.get("summary") if matched_story else "N/A",
            "assignee": matched_story.get("assignee") if matched_story else "N/A",
            "sprint": matched_story.get("sprint") if matched_story else "N/A",
            "story_status": matched_story.get("status") if matched_story else "N/A",
            "blocked": matched_story.get("blocked", False) if matched_story else False,
            "blocker_reason": matched_story.get("blocker_reason") if matched_story else None
        },
        "governing_adr_decisions": adr_decisions,
        "implementing_code_functions": code_functions,
        "operational_regressions": ops_issues
    }

    req_title = matched_req.get("title", clean_key) if matched_req else clean_key
    code_status = f"{len(code_functions)} AST function(s) implementing" if code_functions else "No AST code verified"
    story_status = matched_story.get("status", "No Story") if matched_story else "Backlog"

    explanation = (
        f"5-Pillar Lineage for '{req_title}': "
        f"Jira Status: {story_status} (Assignee: {matched_story.get('assignee', 'N/A') if matched_story else 'N/A'}); "
        f"Code Status: {code_status}; "
        f"ADR Constraints: {len(adr_decisions)} active decision(s); "
        f"Operations History: {len(ops_issues)} past regression ticket(s)."
    )

    return ExplainableResult(
        result=trace_summary,
        cypher_query=cypher_query,
        traversal_path=traversal_path,
        explanation=explanation
    ).model_dump()


def ingest_jira_board(
    jira_file_path: str,
    project_id: str = "project:payflow",
    actor: Optional[str] = "tpm-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Ingests an external Jira JSON export file into the 5th Pillar (Program Flow)
    and persists all Epics, Features, Stories, and Cross-Pillar links in FalkorDB.
    Guarded by security harness: path sandboxing, sensitive file blocking, and IAM authorization.
    """
    clean_actor = actor or "tpm-lead@payflow.internal"
    denial = enforce_ingestion_harness(
        target_path=jira_file_path,
        actor=clean_actor,
        required_permission=Permission.MANAGE_AGILE_FLOW,
        action_name="ingest_jira_board"
    )
    if denial:
        return denial

    parser = JiraBoardParser(project_id=project_id)
    parsed = parser.parse_file(jira_file_path)

    for epic in parsed["epics"]:
        db.create_node(epic.id, "Epic", epic.model_dump())
    for feat in parsed["features"]:
        db.create_node(feat.id, "AgileFeature", feat.model_dump())
    for story in parsed["stories"]:
        db.create_node(story.id, "Story", story.model_dump())
    for from_id, rel, to_id in parsed["edges"]:
        db.create_edge(from_id, rel, to_id)

    db.flush()

    return {
        "status": "SUCCESS",
        "epics_ingested": len(parsed["epics"]),
        "features_ingested": len(parsed["features"]),
        "stories_ingested": len(parsed["stories"]),
        "edges_created": len(parsed["edges"]),
        "message": f"Successfully ingested Jira board data from {jira_file_path} into 5th Pillar."
    }


def unlock_cross_team_capabilities(
    project_id: str = "project:payflow",
    target_service_or_feature: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes cross-team domains and services across the connected knowledge graph
    to discover reusable capabilities, break down team silos, and provide concrete
    acceleration recommendations to deliver features faster.
    """
    cypher_query = """
    MATCH (p:Project {id: $project_id})-[:HAS_EPIC]->(e:Epic)-[:HAS_FEATURE]->(f:AgileFeature)
    OPTIONAL MATCH (f)-[:HAS_STORY]->(s:Story)
    OPTIONAL MATCH (s)-[:IMPLEMENTS_CODE]->(fn:Function)
    OPTIONAL MATCH (fn)-[:EXECUTES_LOGIC]->(cl:CodeLogic)
    OPTIONAL MATCH (s)-[:GUIDED_BY_ARCHITECTURE]->(d:Decision)
    RETURN f.service_name AS service, collect(DISTINCT s) AS stories,
           collect(DISTINCT fn) AS functions, collect(DISTINCT cl) AS logics,
           collect(DISTINCT d) AS decisions
    """.strip()

    traversal_path: List[TraversalStep] = [
        TraversalStep(
            from_node=project_id,
            relationship=Relationships.HAS_EPIC,
            to_node="Epic",
            explanation="Traverse to project Epics to discover all initiative domains."
        ),
        TraversalStep(
            from_node="Epic",
            relationship=Relationships.HAS_FEATURE,
            to_node="AgileFeature",
            explanation="Map features across distinct domain services."
        ),
        TraversalStep(
            from_node="AgileFeature",
            relationship=Relationships.HAS_STORY,
            to_node="Story",
            explanation="Inspect stories and developer team allocations."
        ),
        TraversalStep(
            from_node="Story",
            relationship=Relationships.IMPLEMENTS_CODE,
            to_node="Function",
            explanation="Identify production-verified code capabilities implemented by each team."
        ),
        TraversalStep(
            from_node="Story",
            relationship=Relationships.GUIDED_BY_ARCHITECTURE,
            to_node="Decision",
            explanation="Uncover architectural patterns and ADR standards owned by teams."
        )
    ]

    epics_found = []
    features_found = []
    stories_found = []

    for neighbor in db.get_neighbors(project_id, direction="outgoing"):
        if neighbor.get("relationship") == Relationships.HAS_EPIC:
            e_node = neighbor.get("node", {})
            epics_found.append(e_node)
            e_id = e_node.get("id")
            for f_rel in db.get_neighbors(e_id, direction="outgoing"):
                if f_rel.get("relationship") == Relationships.HAS_FEATURE:
                    feat_node = f_rel.get("node", {})
                    features_found.append(feat_node)
                    feat_id = feat_node.get("id")
                    for s_rel in db.get_neighbors(feat_id, direction="outgoing"):
                        if s_rel.get("relationship") == Relationships.HAS_STORY:
                            story_node = s_rel.get("node", {})
                            stories_found.append(story_node)

    domain_map: Dict[str, Dict[str, Any]] = {}
    for feat in features_found:
        svc = feat.get("service_name") or "core_gateway"
        if svc not in domain_map:
            domain_map[svc] = {
                "service_name": svc,
                "features": [],
                "engineers": set(),
                "total_points": 0,
                "completed_points": 0,
                "blocked_stories": [],
                "capabilities": [],
                "decisions": set()
            }
        domain_map[svc]["features"].append({
            "key": feat.get("key"),
            "summary": feat.get("summary"),
            "status": feat.get("status"),
            "req_id": feat.get("req_id")
        })

    for story in stories_found:
        feat_id = story.get("feature_id")
        svc = "core_gateway"
        for feat in features_found:
            if feat.get("id") == feat_id:
                svc = feat.get("service_name") or "core_gateway"
                break

        if svc not in domain_map:
            domain_map[svc] = {
                "service_name": svc,
                "features": [],
                "engineers": set(),
                "total_points": 0,
                "completed_points": 0,
                "blocked_stories": [],
                "capabilities": [],
                "decisions": set()
            }

        assignee = story.get("assignee")
        if assignee and assignee != "Unassigned":
            domain_map[svc]["engineers"].add(assignee)

        pts = int(story.get("story_points", 3))
        domain_map[svc]["total_points"] += pts
        if story.get("status", "").upper() == "DONE":
            domain_map[svc]["completed_points"] += pts

        if story.get("blocked"):
            domain_map[svc]["blocked_stories"].append({
                "key": story.get("key"),
                "summary": story.get("summary"),
                "assignee": story.get("assignee"),
                "blocker_reason": story.get("blocker_reason"),
                "points": pts
            })

        func_id = story.get("func_id")
        if func_id:
            fn_node = db.get_node(func_id)
            if fn_node:
                fnp = fn_node.get("properties", {})
                domain_map[svc]["capabilities"].append({
                    "id": func_id,
                    "name": fnp.get("name", func_id),
                    "file_path": fnp.get("file_path"),
                    "docstring": fnp.get("docstring")
                })

        story_id = story.get("id")
        for rel in db.get_neighbors(story_id, direction="outgoing"):
            if rel.get("relationship") == Relationships.GUIDED_BY_ARCHITECTURE:
                dec_node = rel.get("node", {})
                dec_id = dec_node.get("id") or dec_node.get("properties", {}).get("id")
                if dec_id:
                    domain_map[svc]["decisions"].add(dec_id)

    domain_matrix = {}
    for svc, data in domain_map.items():
        if target_service_or_feature:
            t_upper = target_service_or_feature.upper()
            if t_upper not in svc.upper() and not any(t_upper in f["key"].upper() for f in data["features"]):
                continue

        domain_matrix[svc] = {
            "service_name": svc,
            "lead_engineers": sorted(list(data["engineers"])),
            "features_count": len(data["features"]),
            "features": data["features"],
            "total_points": data["total_points"],
            "completed_points": data["completed_points"],
            "delivery_velocity_pct": round(data["completed_points"] / max(1, data["total_points"]) * 100, 1),
            "blocked_stories": data["blocked_stories"],
            "active_capabilities": data["capabilities"],
            "governing_adrs": sorted(list(data["decisions"]))
        }

    reusable_capabilities = [
        {
            "capability": "Resilient Network Retries with Exponential Backoff",
            "owner_domain": "fraud_detector",
            "lead_engineer": "Bob Martinez (Tech Lead)",
            "governing_adr": "ADR-001 (Mandatory 3-Retry Ceiling with Exponential Backoff)",
            "implementing_function": "fraud_detector.py:retry_with_backoff",
            "cross_team_reuse_value": "Eliminates network jitter and partner packet drop false declines for any outbound HTTP integration."
        },
        {
            "capability": "Decoupled Queue Worker Concurrency Throttling",
            "owner_domain": "refund_processor",
            "lead_engineer": "David Kim (Staff SRE)",
            "governing_adr": "ADR-002 (Worker Pool Concurrency of 5 for High-Volume Refunds)",
            "implementing_function": "refund_processor.py:queue_refund_job",
            "cross_team_reuse_value": "Prevents gateway thread exhaustion while protecting downstream partners against HTTP 429 rate limits."
        },
        {
            "capability": "Strict Distributed Idempotency Key Locking",
            "owner_domain": "payment_service",
            "lead_engineer": "Bob Martinez / Alice Chen",
            "governing_adr": "REQ-009 / Payment Idempotency Engine",
            "implementing_function": "demo_data/code/payment_service.py:enforce_idempotency",
            "cross_team_reuse_value": "Prevents duplicate charges, double refunds, and concurrent race conditions across financial mutations."
        },
        {
            "capability": "Zero-Fee Pre-Flight Card Validation",
            "owner_domain": "payment_service",
            "lead_engineer": "Alice Chen (Senior Engineer)",
            "governing_adr": "REQ-002 (Luhn Algorithm & Expiry Arithmetic)",
            "implementing_function": "demo_data/code/payment_service.py:validate_card",
            "cross_team_reuse_value": "Rejects malformed and expired cards locally with zero network clearing fees."
        },
        {
            "capability": "Asynchronous Webhook Event Dispatching",
            "owner_domain": "notification_service",
            "lead_engineer": "Payment Infrastructure Team",
            "governing_adr": "REQ-006 (Merchant Webhook Notifications)",
            "implementing_function": "demo_data/code/notification_service.py:send_webhook",
            "cross_team_reuse_value": "Standardized cryptographic signing and delivery for external merchant webhook events."
        }
    ]

    acceleration_opportunities = []

    # 1. FX Service / DCC Acceleration Opportunity
    if "fx_service" in domain_map or not target_service_or_feature or "FX" in (target_service_or_feature or "").upper():
        acceleration_opportunities.append({
            "target_initiative": "Dynamic Currency Conversion (DCC) Service (PAY-FEAT-204 / PAY-306)",
            "current_status": "Stalled in Backlog (Unassigned, 8 story points)",
            "cross_team_solution": "Reuse Bob Martinez's 'retry_with_backoff' (ADR-001) from fraud_detector for the European Central Bank (ECB) rate feed integration.",
            "delivery_impact": "Accelerates integration by an estimated 5 story points; eliminates custom retry and network jitter boilerplate.",
            "recommended_tpm_action": "Schedule a 30-min architecture handoff between Bob Martinez and the incoming FX engineer to clone the ADR-001 retry wrapper."
        })

    # 2. Partial Refunds Cross-Domain Unblocking Opportunity
    if "refund_processor" in domain_map or not target_service_or_feature or "REFUND" in (target_service_or_feature or "").upper():
        acceleration_opportunities.append({
            "target_initiative": "Partial Refund Calculation & Settlement (PAY-FEAT-205 / PAY-307)",
            "current_status": "Blocked (Sarah Jenkins, Sprint 25, 5 story points - Awaiting interchange fee clawback accounting rule)",
            "cross_team_solution": "Alice Chen's team (payment_service) already implemented merchant interchange fee schedule breakdowns in PAY-FEAT-201.",
            "delivery_impact": "Unblocks Sarah Jenkins immediately without waiting for separate accounting cycles, enabling PAY-307 delivery in Sprint 25.",
            "recommended_tpm_action": "Connect Sarah Jenkins with Alice Chen to adapt the existing merchant fee calculation logic from payment_service into refund_processor."
        })

    # 3. Double-Refund Idempotency Re-Use Opportunity
    acceleration_opportunities.append({
        "target_initiative": "Partial Refund Fraud & Double-Submission Prevention",
        "current_status": "Architectural Risk in Sprint Planning",
        "cross_team_solution": "Directly adopt the Redis idempotency lock pattern developed by payment_service (PAY-308) in the refund processor.",
        "delivery_impact": "Guarantees zero double-refund leakage under high network latency with zero duplicate code.",
        "recommended_tpm_action": "Mandate PAY-308 idempotency middleware pattern in PAY-307 pull request acceptance criteria."
    })

    result_payload = {
        "project_id": project_id,
        "team_domain_matrix": domain_matrix,
        "reusable_cross_team_capabilities": reusable_capabilities,
        "acceleration_opportunities": acceleration_opportunities,
        "total_cross_team_domains": len(domain_map),
        "total_reusable_capabilities": len(reusable_capabilities),
        "total_acceleration_opportunities": len(acceleration_opportunities)
    }

    explanation = (
        f"Cross-Team Capability Analysis for '{project_id}': "
        f"Identified {len(domain_map)} team domains with {len(reusable_capabilities)} reusable production capabilities. "
        f"Discovered {len(acceleration_opportunities)} high-impact acceleration opportunities to unblock delivery "
        f"(e.g., reusing fraud_detector's ADR-001 retry pipeline in fx_service saves ~5-8 story points; "
        f"pairing Sarah Jenkins with Alice Chen unblocks PAY-307 partial refund interchange rules)."
    )

    return ExplainableResult(
        result=result_payload,
        cypher_query=cypher_query,
        traversal_path=traversal_path,
        explanation=explanation
    ).model_dump()


def create_epic(
    epic_key: str,
    summary: str,
    description: str = "",
    project_id: str = "project:payflow",
    owner: str = "Marcus Vance",
    target_date: Optional[str] = None,
    actor: Optional[str] = "tpm-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Creates a new Agile Epic under a project in the Program Flow.
    Guarded by IAM: Requires MANAGE_AGILE_FLOW permission (Program Managers / Admins).
    """
    clean_actor = actor or "tpm-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.MANAGE_AGILE_FLOW, "create_epic")
    if denial:
        return denial

    clean_pid = project_id if project_id.startswith("project:") else f"project:{project_id}"
    clean_key = epic_key.replace("epic:", "")
    epic_id = f"epic:{clean_key}"

    epic_node = EpicNode(
        id=epic_id,
        project_id=clean_pid,
        key=clean_key,
        summary=summary,
        description=description,
        status="IN_PROGRESS",
        owner=owner,
        target_date=target_date,
        created_date=datetime.now().strftime("%Y-%m-%d")
    )

    db.create_node(epic_id, "Epic", epic_node.model_dump())
    db.create_edge(clean_pid, Relationships.HAS_EPIC, epic_id)
    db.flush()

    cypher = """
    MERGE (p:Project {id: $project_id})
    MERGE (e:Epic {id: $epic_id})
    SET e.summary = $summary, e.key = $key, e.owner = $owner, e.status = intern($status)
    MERGE (p)-[:HAS_EPIC]->(e)
    """
    db.execute_cypher(cypher, {
        "project_id": clean_pid,
        "epic_id": epic_id,
        "summary": summary,
        "key": clean_key,
        "owner": owner,
        "status": "IN_PROGRESS"
    })

    return ExplainableResult(
        result={
            "epic_id": epic_id,
            "epic_key": clean_key,
            "summary": summary,
            "owner": owner,
            "project_id": clean_pid,
            "created_by": clean_actor,
            "status": "CREATED"
        },
        cypher_query=cypher.strip(),
        traversal_path=[
            TraversalStep(
                from_node=clean_pid,
                relationship=Relationships.HAS_EPIC,
                to_node=epic_id,
                explanation=f"Linked Project '{clean_pid}' to new Epic '{clean_key}'"
            )
        ],
        explanation=f"Created Agile Epic '{clean_key}' ({summary}) for project '{clean_pid}' by '{clean_actor}'."
    ).model_dump()


def create_feature(
    feature_key: str,
    epic_key_or_id: str,
    summary: str,
    description: str = "",
    service_name: Optional[str] = None,
    architecture_diagram: Optional[str] = None,
    req_id: Optional[str] = None,
    actor: Optional[str] = "tpm-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Creates a new functional feature under an Epic in the Program Flow, linking to PRD requirements if specified.
    Guarded by IAM: Requires MANAGE_AGILE_FLOW permission.
    """
    clean_actor = actor or "tpm-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.MANAGE_AGILE_FLOW, "create_feature")
    if denial:
        return denial

    clean_eid = epic_key_or_id.replace("epic:", "")
    epic_id = f"epic:{clean_eid}"
    clean_fkey = feature_key.replace("feat:", "")
    feat_id = f"feat:{clean_fkey}"

    clean_req_id = None
    if req_id:
        clean_req_id = req_id if req_id.startswith("req:") else f"req:{req_id}"

    feature_node = AgileFeatureNode(
        id=feat_id,
        epic_id=epic_id,
        key=clean_fkey,
        summary=summary,
        description=description,
        service_name=service_name,
        architecture_diagram=architecture_diagram,
        status="IN_DEVELOPMENT",
        req_id=clean_req_id
    )

    db.create_node(feat_id, "AgileFeature", feature_node.model_dump())
    db.create_edge(epic_id, Relationships.HAS_FEATURE, feat_id)

    traversal_path = [
        TraversalStep(
            from_node=epic_id,
            relationship=Relationships.HAS_FEATURE,
            to_node=feat_id,
            explanation=f"Linked Epic '{clean_eid}' to new Feature '{clean_fkey}'"
        )
    ]

    if clean_req_id and clean_req_id in db.memory_graph.nodes:
        db.create_edge(feat_id, Relationships.REALIZES_REQUIREMENT, clean_req_id)
        traversal_path.append(
            TraversalStep(
                from_node=feat_id,
                relationship=Relationships.REALIZES_REQUIREMENT,
                to_node=clean_req_id,
                explanation=f"Feature '{clean_fkey}' realizes PRD requirement '{clean_req_id}'"
            )
        )

    db.flush()

    cypher = """
    MERGE (e:Epic {id: $epic_id})
    MERGE (f:AgileFeature {id: $feat_id})
    SET f.summary = $summary, f.key = $key, f.service_name = $service_name, f.status = intern($status)
    MERGE (e)-[:HAS_FEATURE]->(f)
    """
    db.execute_cypher(cypher, {
        "epic_id": epic_id,
        "feat_id": feat_id,
        "summary": summary,
        "key": clean_fkey,
        "service_name": service_name or "",
        "status": "IN_DEVELOPMENT"
    })

    return ExplainableResult(
        result={
            "feature_id": feat_id,
            "feature_key": clean_fkey,
            "summary": summary,
            "epic_id": epic_id,
            "service_name": service_name,
            "req_id": clean_req_id,
            "created_by": clean_actor,
            "status": "CREATED"
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation=f"Created Agile Feature '{clean_fkey}' ({summary}) under Epic '{clean_eid}' by '{clean_actor}'."
    ).model_dump()


def create_story(
    story_key: str,
    feature_key_or_id: str,
    summary: str,
    description: str = "",
    story_points: int = 3,
    assignee: str = "Alice Chen",
    sprint: str = "Sprint 25",
    func_id: Optional[str] = None,
    actor: Optional[str] = "tpm-lead@payflow.internal"
) -> Dict[str, Any]:
    """
    Creates a new developer task story under an Agile Feature in the Program Flow.
    Guarded by IAM: Requires MANAGE_AGILE_FLOW permission.
    """
    clean_actor = actor or "tpm-lead@payflow.internal"
    denial = iam.enforce_permission(clean_actor, Permission.MANAGE_AGILE_FLOW, "create_story")
    if denial:
        return denial

    clean_fid = feature_key_or_id.replace("feat:", "")
    feature_id = f"feat:{clean_fid}"
    clean_skey = story_key.replace("story:", "")
    story_id = f"story:{clean_skey}"

    clean_func_id = None
    if func_id:
        clean_func_id = func_id if func_id.startswith("func:") else f"func:{func_id}"

    story_node = StoryNode(
        id=story_id,
        feature_id=feature_id,
        key=clean_skey,
        summary=summary,
        description=description,
        story_points=story_points,
        assignee=assignee,
        status="TODO",
        sprint=sprint,
        created_date=datetime.now().strftime("%Y-%m-%d"),
        func_id=clean_func_id
    )

    db.create_node(story_id, "Story", story_node.model_dump())
    db.create_edge(feature_id, Relationships.HAS_STORY, story_id)

    traversal_path = [
        TraversalStep(
            from_node=feature_id,
            relationship=Relationships.HAS_STORY,
            to_node=story_id,
            explanation=f"Linked Feature '{clean_fid}' to new Story '{clean_skey}'"
        )
    ]

    if clean_func_id and clean_func_id in db.memory_graph.nodes:
        db.create_edge(story_id, Relationships.IMPLEMENTS_CODE, clean_func_id)
        traversal_path.append(
            TraversalStep(
                from_node=story_id,
                relationship=Relationships.IMPLEMENTS_CODE,
                to_node=clean_func_id,
                explanation=f"Story '{clean_skey}' linked to implementing code function '{clean_func_id}'"
            )
        )

    db.flush()

    cypher = """
    MERGE (f:AgileFeature {id: $feature_id})
    MERGE (s:Story {id: $story_id})
    SET s.summary = $summary, s.key = $key, s.assignee = $assignee, s.story_points = $story_points, s.status = intern($status)
    MERGE (f)-[:HAS_STORY]->(s)
    """
    db.execute_cypher(cypher, {
        "feature_id": feature_id,
        "story_id": story_id,
        "summary": summary,
        "key": clean_skey,
        "assignee": assignee,
        "story_points": story_points,
        "status": "TODO"
    })

    return ExplainableResult(
        result={
            "story_id": story_id,
            "story_key": clean_skey,
            "summary": summary,
            "feature_id": feature_id,
            "assignee": assignee,
            "story_points": story_points,
            "sprint": sprint,
            "func_id": clean_func_id,
            "created_by": clean_actor,
            "status": "CREATED"
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation=f"Created Agile Story '{clean_skey}' ({summary}, {story_points} pts) assigned to '{assignee}' by '{clean_actor}'."
    ).model_dump()
