"""
CodeGraph Model Context Protocol (MCP) Server.
Exposes graph reasoning, PRD verification, and engineering safety tools to AI agents.
Supports both stdio (for local Claude/Antigravity/Cursor) and streamable-http/sse (for cloud/production microservices).
"""

import sys
import logging
from typing import Dict, Any, List, Optional
from mcp.server.mcpserver import MCPServer
from .config import settings
from .db import db
from .tools.product_tools import (
    query_prd_coverage as _query_prd_coverage,
    simulate_scenario as _simulate_scenario,
    get_change_history as _get_change_history,
    list_uncovered_requirements as _list_uncovered_requirements,
    update_prd_features_and_scenarios as _update_prd_features_and_scenarios,
    approve_prd_update_via_email as _approve_prd_update_via_email,
)
from .tools.developer_tools import (
    debug_issue as _debug_issue,
    check_safe_to_change as _check_safe_to_change,
    get_function_lineage as _get_function_lineage,
    review_pr_diff as _review_pr_diff,
    cross_org_bug_check as _cross_org_bug_check,
)
from .tools.shared_tools import (
    search_graph as _search_graph,
    get_related_entities as _get_related_entities,
    explain_traversal as _explain_traversal,
)
from .tools.ingest_tools import (
    ingest_codebase as _ingest_codebase,
    ingest_prd as _ingest_prd,
    ingest_adr as _ingest_adr,
    ingest_runbook as _ingest_runbook,
    record_bugfix as _record_bugfix,
    approve_bugfix_via_email as _approve_bugfix_via_email,
)
from .tools.program_tools import (
    query_program_delivery_status as _query_program_delivery_status,
    diagnose_delivery_bottlenecks as _diagnose_delivery_bottlenecks,
    get_feature_lead_time_metrics as _get_feature_lead_time_metrics,
    trace_requirement_to_delivery_chain as _trace_requirement_to_delivery_chain,
    ingest_jira_board as _ingest_jira_board,
    unlock_cross_team_capabilities as _unlock_cross_team_capabilities,
)

logger = logging.getLogger("codegraph.mcp")

# Initialize MCP Server
server = MCPServer(
    name="codegraph",
    instructions=(
        "CodeGraph MCP Server: 5-Pillar Connected Knowledge Graph bridging Code AST, PRDs, ADRs, Operations, and Program Flow. "
        "Use Product Tools (query_prd_coverage, simulate_scenario, get_change_history, list_uncovered_requirements) "
        "for business/product queries. "
        "Use Developer Tools (debug_issue, check_safe_to_change, get_function_lineage, review_pr_diff, cross_org_bug_check) "
        "for engineering diagnostics and safety checks. "
        "Use Program Tools (query_program_delivery_status, diagnose_delivery_bottlenecks, get_feature_lead_time_metrics, trace_requirement_to_delivery_chain, unlock_cross_team_capabilities) "
        "for agile sprint velocity, blocked dependency diagnosis, cross-team capability unlocking, and PRD-to-code delivery tracking. "
        "Every tool returns explainable results with the underlying Cypher query and graph traversal path."
    )
)


# =========================================================================
# Product Persona Tools
# =========================================================================

@server.tool(
    name="query_prd_coverage",
    description="Calculate PRD requirement coverage across the codebase. Returns percentage implemented, active functions, and missing requirements in plain English."
)
def query_prd_coverage(prd_id: Optional[str] = None) -> Dict[str, Any]:
    return _query_prd_coverage(prd_id=prd_id)


@server.tool(
    name="simulate_scenario",
    description="Simulate how the system behaves for a business scenario (e.g. 'expired card', 'refund after 30 days') using multi-hop graph traversal. Explains in plain English without raw code."
)
def simulate_scenario(scenario_query: str) -> Dict[str, Any]:
    return _simulate_scenario(scenario_query=scenario_query)


@server.tool(
    name="get_change_history",
    description="Retrieve the chronological timeline of changes with explicit reasons (PRD requirement, bug fix, or ADR architecture decision). Ideal for understanding WHAT changed and WHY."
)
def get_change_history(from_date: Optional[str] = None, keyword: Optional[str] = None) -> Dict[str, Any]:
    return _get_change_history(from_date=from_date, keyword=keyword)


@server.tool(
    name="list_uncovered_requirements",
    description="List all PRD business requirements that currently have zero implementing code functions in the graph. Useful for gap analysis."
)
def list_uncovered_requirements() -> Dict[str, Any]:
    return _list_uncovered_requirements()


@server.tool(
    name="update_prd_features_and_scenarios",
    description="Propose or add a new business requirement/feature and test scenarios to the PRD. Dispatches an approval email to the project's PRD Owner."
)
def update_prd_features_and_scenarios(
    feature_id: str,
    feature_title: str,
    description: str,
    project_id: str = "project:payflow",
    priority: str = "HIGH",
    scenarios: Optional[List[str]] = None,
    guardrails: Optional[List[str]] = None,
    approved_by_prd_owner: bool = False
) -> Dict[str, Any]:
    return _update_prd_features_and_scenarios(
        feature_id=feature_id,
        feature_title=feature_title,
        description=description,
        project_id=project_id,
        priority=priority,
        scenarios=scenarios,
        guardrails=guardrails,
        approved_by_prd_owner=approved_by_prd_owner
    )


@server.tool(
    name="approve_prd_update_via_email",
    description="Validate PRD Owner's email approval token and permanently ingest the new feature and scenarios into FalkorDB."
)
def approve_prd_update_via_email(
    feature_id: str,
    approval_token: str,
    approver_email: Optional[str] = None
) -> Dict[str, Any]:
    return _approve_prd_update_via_email(
        feature_id=feature_id,
        approval_token=approval_token,
        approver_email=approver_email
    )


# =========================================================================
# Developer Persona Tools
# =========================================================================


@server.tool(
    name="debug_issue",
    description="Diagnose a production error or stack trace (e.g. 'REFUND_TIMEOUT'). Matches past BugFixes and Runbooks, providing Root Cause Analysis (RCA), affected files/lines, and verified fix steps."
)
def debug_issue(error_logs: str) -> Dict[str, Any]:
    return _debug_issue(error_logs=error_logs)


@server.tool(
    name="check_safe_to_change",
    description="Audit whether modifying a function is safe. Cross-references governing ADR architectural constraints, past regression bugs, and PRD dependencies."
)
def check_safe_to_change(function_name: str, proposed_change: Optional[str] = None) -> Dict[str, Any]:
    return _check_safe_to_change(function_name=function_name, proposed_change=proposed_change)


@server.tool(
    name="get_function_lineage",
    description="Retrieve full history and lineage of a function: why it was built, which PRD requirements it serves, which ADRs govern it, and all past commits and bug fixes."
)
def get_function_lineage(function_name: str) -> Dict[str, Any]:
    return _get_function_lineage(function_name=function_name)


@server.tool(
    name="review_pr_diff",
    description="Audit a list of modified functions in a PR. Flags any touched functions that violate architectural decisions or have known historical regression bug patterns."
)
def review_pr_diff(modified_functions: List[str], diff_summary: Optional[str] = None) -> Dict[str, Any]:
    return _review_pr_diff(modified_functions=modified_functions, diff_summary=diff_summary)


@server.tool(
    name="cross_org_bug_check",
    description="Search past bug fixes and RCAs across services in the organization by symptom or keyword pattern."
)
def cross_org_bug_check(symptom_pattern: str) -> Dict[str, Any]:
    return _cross_org_bug_check(symptom_pattern=symptom_pattern)


# =========================================================================
# Shared Exploration Tools
# =========================================================================

@server.tool(
    name="search_graph",
    description="Full-text search across all nodes in the knowledge graph (PRDs, Requirements, Code, ADRs, BugFixes, Runbooks)."
)
def search_graph(query: str, entity_type: Optional[str] = None, limit: int = 15) -> Dict[str, Any]:
    return _search_graph(query=query, entity_type=entity_type, limit=limit)


@server.tool(
    name="get_related_entities",
    description="Explore the graph neighborhood up to N hops from any node ID to discover connected business and code entities."
)
def get_related_entities(node_id: str, hops: int = 2) -> Dict[str, Any]:
    return _get_related_entities(node_id=node_id, hops=hops)


@server.tool(
    name="explain_traversal",
    description="Visualizes a list of traversal steps as an ASCII diagram to explain how an answer was derived from connected graph nodes."
)
def explain_traversal(steps: List[Dict[str, Any]]) -> str:
    return _explain_traversal(steps=steps)


# =========================================================================
# Ingestion Tools (Live Graph Updates)
# =========================================================================

@server.tool(
    name="ingest_codebase",
    description="Ingest source code files from a directory into AST graph nodes (Files, Classes, Functions, and Call edges)."
)
def ingest_codebase(directory_path: str) -> Dict[str, Any]:
    return _ingest_codebase(directory_path=directory_path)


@server.tool(
    name="ingest_prd",
    description="Ingest a PRD markdown document into PRD, Requirement, and Scenario graph nodes."
)
def ingest_prd(file_path: str) -> Dict[str, Any]:
    return _ingest_prd(file_path=file_path)


@server.tool(
    name="ingest_adr",
    description="Ingest an Architecture Decision Record markdown file into ADR, Decision, and Constraint nodes."
)
def ingest_adr(file_path: str) -> Dict[str, Any]:
    return _ingest_adr(file_path=file_path)


@server.tool(
    name="ingest_runbook",
    description="Ingest an operational runbook markdown file into Runbooks, BugFixes, and verified recovery procedures."
)
def ingest_runbook(file_path: str) -> Dict[str, Any]:
    return _ingest_runbook(file_path=file_path)


@server.tool(
    name="record_bugfix",
    description="Record a resolved production bug, RCA, and fix into the graph. Has a mandatory human lead approval flag."
)
def record_bugfix(
    ticket_id: str,
    symptom: str,
    rca: str,
    fix_summary: str,
    affected_function_name: str,
    approved_by_lead: bool = False,
    date: str = "2026-10-17"
) -> Dict[str, Any]:
    return _record_bugfix(
        ticket_id=ticket_id,
        symptom=symptom,
        rca=rca,
        fix_summary=fix_summary,
        affected_function_name=affected_function_name,
        approved_by_lead=approved_by_lead,
        date=date
    )


@server.tool(
    name="approve_bugfix_via_email",
    description="Validate Code Domain Owner's email approval token and permanently ingest the BugFix/RCA into FalkorDB."
)
def approve_bugfix_via_email(
    ticket_id: str,
    approval_token: str,
    approver_email: Optional[str] = None
) -> Dict[str, Any]:
    return _approve_bugfix_via_email(
        ticket_id=ticket_id,
        approval_token=approval_token,
        approver_email=approver_email
    )


# =========================================================================
# Program Manager Persona Tools (5th Pillar: Agile / Jira Delivery)
# =========================================================================

@server.tool(
    name="query_program_delivery_status",
    description="Query overall agile delivery progress, sprint velocity, completed vs remaining story points, and active blockers across Epics, Features, and Stories."
)
def query_program_delivery_status(
    project_id: str = "project:payflow",
    epic_id: Optional[str] = None
) -> Dict[str, Any]:
    return _query_program_delivery_status(project_id=project_id, epic_id=epic_id)


@server.tool(
    name="diagnose_delivery_bottlenecks",
    description="Diagnose root-cause gaps and delivery blockers between PRD requirements and engineering code (definition gaps, active blockers, ghost deliveries)."
)
def diagnose_delivery_bottlenecks(
    project_id: str = "project:payflow"
) -> Dict[str, Any]:
    return _diagnose_delivery_bottlenecks(project_id=project_id)


@server.tool(
    name="get_feature_lead_time_metrics",
    description="Analyze engineering cycle times and lead times for converting PRD requirements into architecture and code."
)
def get_feature_lead_time_metrics(
    project_id: str = "project:payflow",
    feature_id: Optional[str] = None
) -> Dict[str, Any]:
    return _get_feature_lead_time_metrics(project_id=project_id, feature_id=feature_id)


@server.tool(
    name="trace_requirement_to_delivery_chain",
    description="Trace 5-pillar lineage for any requirement, ticket, or function: PRD <-> Jira Epic/Story <-> ADR <-> CodeBase <-> Operations."
)
def trace_requirement_to_delivery_chain(
    req_id_or_ticket: str,
    project_id: str = "project:payflow"
) -> Dict[str, Any]:
    return _trace_requirement_to_delivery_chain(req_id_or_ticket=req_id_or_ticket, project_id=project_id)


@server.tool(
    name="ingest_jira_board",
    description="Ingest external Jira board JSON export into the 5th Pillar (Program Flow) and persist in FalkorDB."
)
def ingest_jira_board(
    jira_file_path: str,
    project_id: str = "project:payflow"
) -> Dict[str, Any]:
    return _ingest_jira_board(jira_file_path=jira_file_path, project_id=project_id)


@server.tool(
    name="unlock_cross_team_capabilities",
    description="Analyze cross-team domains and services across the connected knowledge graph to discover reusable capabilities, break down team silos, and provide concrete acceleration recommendations to deliver features faster."
)
def unlock_cross_team_capabilities(
    project_id: str = "project:payflow",
    target_service_or_feature: Optional[str] = None
) -> Dict[str, Any]:
    return _unlock_cross_team_capabilities(project_id=project_id, target_service_or_feature=target_service_or_feature)


# =========================================================================
# Predefined Agent Prompts
# =========================================================================

@server.prompt(name="product_advisor", description="Persona for Product Managers: Plain English, no code snippets")
def product_advisor_prompt() -> str:
    return (
        "You are CodeGraph Product Advisor, an expert assistant for Product Managers. "
        "Your role is to verify PRD compliance, simulate business scenarios, and explain changes. "
        "ROLES AND RESPONSIBILITIES: "
        "1. Primary Role: Business Specification & Requirements Authority for the project. "
        "2. Core Responsibilities: PRD compliance auditing (query_prd_coverage, list_uncovered_requirements), business scenario simulation (simulate_scenario), agent-driven PRD updates with acceptance scenarios (update_prd_features_and_scenarios), routing approvals to the project PRD Owner (Project.prd_owner) via email, and change audit trails (get_change_history). "
        "3. Boundaries & Exclusions: NEVER output code snippets, programming syntax, or function names directly unless explicitly asked. Never bypass the PRD Owner's approval gate. Do not manage agile sprint allocation (delegate to Program Manager). "
        "RULES: "
        "1. NEVER output code snippets, programming syntax, or function names directly unless explicitly asked. "
        "2. Explain everything in plain English using business concepts and percentage metrics. "
        "3. Always call query_prd_coverage, simulate_scenario, or list_uncovered_requirements to ground your answers in the graph. "
        "4. Include the explainable traversal path summary to show which business requirements were analyzed."
    )


@server.prompt(name="developer_assistant", description="Persona for Engineers: Technical diagnostics, code locations, ADR constraints")
def developer_assistant_prompt() -> str:
    return (
        "You are CodeGraph Senior Engineering Assistant. "
        "Your role is to triage production incidents, provide Root Cause Analyses (RCA), and conduct safety audits before developers override code. "
        "ROLES AND RESPONSIBILITIES: "
        "1. Primary Role: Engineering Implementation & Architectural Resilience Authority for the codebase. "
        "2. Core Responsibilities: Architectural safety audits before edits (check_safe_to_change), production incident RCA diagnostics (debug_issue), quality & function lineage (get_function_lineage), PR diff review against ADRs (review_pr_diff), cross-org bug pattern checks (cross_org_bug_check), and staging bugfixes for Code Domain Owner email signoff (record_bugfix). "
        "3. Boundaries & Exclusions: NEVER recommend lowering retry counts or violating ADRs. NEVER bypass the Code Domain Owner's email signoff. Do not redefine business scope or manage sprint timelines. "
        "RULES: "
        "1. Always include exact file paths, line numbers, and error codes when answering. "
        "2. Before recommending modifying any function, ALWAYS call check_safe_to_change to inspect governing ADRs and past regression bugs. "
        "3. When debugging incidents, query debug_issue to match past incident runbooks. "
        "4. Ground all recommendations in the graph data and cite governing ADR IDs (e.g. ADR-001, ADR-002)."
    )


@server.prompt(name="program_manager", description="Persona for Technical Program Managers: Velocity, sprint health, blockers, PRD-to-code gap diagnosis")
def program_manager_prompt() -> str:
    return (
        "You are CodeGraph Program Advisor, an autonomous delivery intelligence assistant for Technical Program Managers (TPMs) and Agile Delivery Leads. "
        "Your role is to monitor project velocity, sprint health, cycle time, blocked dependencies, diagnose root-cause bottlenecks between PRDs and code, and unlock cross-team capabilities to accelerate delivery. "
        "ROLES AND RESPONSIBILITIES: "
        "1. Primary Role: Delivery Velocity, Agile Workflow Governance, Cross-Team Capability Unlocking, and Cross-Discipline Alignment Authority. "
        "2. Core Responsibilities: Agile program delivery tracking across Epics, Features, and Stories (query_program_delivery_status), root-cause bottleneck diagnosis (diagnose_delivery_bottlenecks for definition gaps, active blockers, ghost deliveries), unlocking cross-team domain capabilities and pattern reuse (unlock_cross_team_capabilities), feature lead time and cycle time metrics (get_feature_lead_time_metrics), 5-pillar bidirectional requirement-to-code traceability (trace_requirement_to_delivery_chain), and Jira sprint board ingestion (ingest_jira_board). "
        "3. Boundaries & Exclusions: NEVER output raw programming source code or AST syntax. NEVER unilaterally approve PRD scope changes (reserved for PRD Owner) or architectural fixes (reserved for Code Domain Owner). Focus exclusively on delivery progress, unblocking dependencies, cycle times, cross-team capability reuse, and cross-team alignment. "
        "RULES: "
        "1. Speak in program management language: story points, sprint burndown, cycle times, blocked dependencies, release readiness %. "
        "2. Pinpoint the exact breakdown: definition gap, architecture delay, active engineering blocker, or ghost delivery. "
        "3. Always ground answers by calling query_program_delivery_status, diagnose_delivery_bottlenecks, get_feature_lead_time_metrics, trace_requirement_to_delivery_chain, or unlock_cross_team_capabilities. "
        "4. Proactively surface blocked stories with assignee names, specific blocker reasons, and cross-team capability reuse opportunities to accelerate delivery."
    )


def start_server():
    """Starts the MCP server based on configured transport."""
    transport = settings.mcp_transport
    logger.info(f"Starting CodeGraph MCP server on transport: {transport}")

    if transport in ("streamable-http", "http"):
        server.run(transport="streamable-http", host=settings.mcp_http_host, port=settings.mcp_http_port)
    elif transport == "sse":
        server.run(transport="sse", host=settings.mcp_http_host, port=settings.mcp_http_port)
    else:
        # Default: stdio
        server.run(transport="stdio")


if __name__ == "__main__":
    start_server()
