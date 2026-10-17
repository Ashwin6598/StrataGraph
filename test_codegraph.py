"""
Comprehensive Test Suite for CodeGraph (4-Pillar Data Model).
Validates Knowledge Graph Ingestion, 4-Pillar Chains, Cross-Entity Interlinks, and Timeline Lineage.
"""

import pytest
from codegraph.db import db
from codegraph.tools.product_tools import (
    query_prd_coverage,
    simulate_scenario,
    get_change_history,
    list_uncovered_requirements,
)
from codegraph.tools.developer_tools import (
    debug_issue,
    check_safe_to_change,
    get_function_lineage,
    review_pr_diff,
    cross_org_bug_check,
)
from codegraph.tools.shared_tools import (
    search_graph,
    get_related_entities,
    explain_traversal,
)
from codegraph.tools.ingest_tools import record_bugfix
from codegraph.mcp_server import server
from seed import seed_all


@pytest.fixture(scope="session", autouse=True)
def setup_graph():
    """Ensure graph is freshly seeded before tests execute."""
    seed_all()


def test_4_pillar_graph_seeding_integrity():
    """Verify that nodes across all 4 pillar chains, Project root, and Timeline exist."""
    assert len(db.memory_graph.nodes) >= 60, "Graph should contain at least 60 nodes"
    assert len(db.memory_graph.edges) >= 120, "Graph should contain at least 120 edges"

    labels = {n["label"] for n in db.memory_graph.nodes.values()}

    # Anchor
    assert "Project" in labels

    # CodeBase Chain: Project -> CodeInput -> LogicFlow -> Class -> Function -> CodeLogic -> CodeOutput
    assert "CodeInput" in labels
    assert "LogicFlow" in labels
    assert "Class" in labels
    assert "Function" in labels
    assert "CodeLogic" in labels
    assert "CodeOutput" in labels

    # PRD Chain: Project -> PRDInput -> FunctionalRequirement -> Guardrail -> PRDOutput
    assert "PRDInput" in labels
    assert "FunctionalRequirement" in labels
    assert "Guardrail" in labels
    assert "PRDOutput" in labels

    # ADR Chain: Project -> ADRRequirement -> Architecture -> Decision -> ADRResult
    assert "ADRRequirement" in labels
    assert "Architecture" in labels
    assert "Decision" in labels
    assert "ADRResult" in labels

    # Operations Chain: Project -> Issue -> RCA -> Fix -> OpResult
    assert "Issue" in labels
    assert "RCA" in labels
    assert "Fix" in labels
    assert "OpResult" in labels

    # Timeline & History
    assert "ChangeTimeline" in labels


def test_product_query_prd_coverage():
    """Verify PRD coverage calculation across FunctionalRequirements."""
    res = query_prd_coverage()
    data = res["result"]

    assert data["total_requirements"] == 9
    assert data["implemented_count"] == 7
    assert data["unimplemented_count"] == 2
    assert "77.8%" in data["coverage_percentage"]

    # Verify unimplemented requirements
    missing_ids = [m["id"] for m in data["missing_requirements"]]
    assert "REQ-004" in missing_ids  # Multi-currency DCC
    assert "REQ-008" in missing_ids  # Partial refunds

    # Verify explainability
    assert "Project" in res["cypher_query"]
    assert len(res["traversal_path"]) > 0


def test_product_simulate_scenario():
    """Verify multi-hop business scenario simulation traversing Guardrail and PRDOutput."""
    res = simulate_scenario("expired card")
    data = res["result"]

    assert len(data["matched_guardrails"]) > 0
    top = data["matched_guardrails"][0]
    assert "CARD_EXPIRED" in top["violation_code"]
    assert top["handled_in_code"] is True
    assert "validate_card" in top["workflow_components"]

    # Verify explainability
    assert "MATCH (pi:PRDInput)" in res["cypher_query"]
    assert len(res["traversal_path"]) > 0


def test_product_get_change_history():
    """Verify change history timeline with 'what changed' and 'why changed'."""
    res = get_change_history()
    data = res["result"]

    assert data["total_changes"] >= 4
    for record in data["timeline"]:
        assert "what_changed" in record
        assert "why_changed" in record
        assert "date" in record

    categories = {c["category"] for c in data["timeline"]}
    assert "PRD_FEATURE" in categories
    assert "ADR_ENFORCEMENT" in categories
    assert "OPERATION_FIX" in categories


def test_product_list_uncovered_requirements():
    """Verify detection of unstarted requirements."""
    res = list_uncovered_requirements()
    data = res["result"]

    assert data["uncovered_count"] == 2
    ids = {r["id"] for r in data["uncovered_requirements"]}
    assert "REQ-004" in ids
    assert "REQ-008" in ids


def test_developer_debug_issue():
    """Verify incident triage matching BUG-342 and RCA."""
    res = debug_issue("REFUND_TIMEOUT on order #4521")
    data = res["result"]

    assert len(data["matched_incidents"]) > 0
    top = data["matched_incidents"][0]
    assert top["ticket_id"] == "BUG-342"
    assert "concurrency" in top["root_cause_analysis"].lower()
    assert any("ADR-002" in adr for adr in top["violated_adr"])

    # Verify affected code location
    assert len(top["affected_code_locations"]) > 0
    loc = top["affected_code_locations"][0]
    assert "refund_processor.py" in loc["file"]


def test_developer_check_safe_to_change():
    """Verify safety audit on retry_with_backoff governed by ADR-001."""
    res = check_safe_to_change("retry_with_backoff")
    data = res["result"]

    assert data["safe_to_modify"] is False
    assert "UNSAFE" in data["safety_verdict"]
    assert any("ADR-001" in a for a in data["governing_adrs"])
    assert any("BUG-112" in i for i in data["past_issues"])


def test_developer_get_function_lineage():
    """Verify evolutionary history and timeline of retry_with_backoff."""
    res = get_function_lineage("retry_with_backoff")
    data = res["result"]

    assert data["function"] == "retry_with_backoff"
    assert len(data["governing_adrs"]) > 0
    assert len(data["timeline_history"]) > 0


def test_developer_review_pr_diff():
    """Verify PR diff safety evaluation."""
    res = review_pr_diff(["retry_with_backoff", "send_webhook"])
    data = res["result"]

    assert data["blocking_risk"] is True
    assert "REQUEST_CHANGES" in data["pr_verdict"]


def test_developer_cross_org_bug_check():
    """Verify pattern matching across past issues."""
    res = cross_org_bug_check("concurrency")
    data = res["result"]

    assert data["found_matches_count"] >= 1
    assert any("BUG-342" in m["ticket"] for m in data["historical_issues"])


def test_shared_search_and_neighborhood():
    """Verify free-text search and multi-hop neighborhood expansion."""
    search_res = search_graph("fraud")
    assert search_res["result"]["total_matches"] > 0

    # Expand 2 hops from project:payflow
    neigh_res = get_related_entities("project:payflow", hops=2)
    assert neigh_res["result"]["connected_entities_count"] > 0


def test_ingest_record_bugfix_approval_workflow():
    """Verify recording a new bug fix with approval gate into Operations chain."""
    unapp = record_bugfix(
        ticket_id="BUG-999",
        symptom="Currency symbol parsing error",
        rca="Regex failed on non-ASCII currency signs",
        fix_summary="Updated regex pattern to unicode",
        affected_function_name="validate_card",
        approved_by_lead=False
    )
    assert unapp["result"]["status"] == "PENDING_APPROVAL"
    assert unapp["result"]["approved"] is False

    app = record_bugfix(
        ticket_id="BUG-1000",
        symptom="Card whitespace stripping",
        rca="Missing strip before Luhn",
        fix_summary="Added strip call",
        affected_function_name="validate_card",
        approved_by_lead=True
    )
    assert app["result"]["status"] == "APPROVED"
    assert app["result"]["approved"] is True


def test_mcp_server_registration():
    """Verify MCP Server lists all 15 tools and predefined prompts."""
    tool_names = [t.name for t in server._tool_manager.list_tools()]
    expected_tools = [
        "query_prd_coverage",
        "simulate_scenario",
        "get_change_history",
        "list_uncovered_requirements",
        "debug_issue",
        "check_safe_to_change",
        "get_function_lineage",
        "review_pr_diff",
        "cross_org_bug_check",
        "search_graph",
        "get_related_entities",
        "explain_traversal",
        "ingest_codebase",
        "ingest_prd",
        "ingest_adr",
        "ingest_runbook",
        "record_bugfix"
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Expected tool {exp} to be registered in MCP server"

    prompt_names = [p.name for p in server._prompt_manager.list_prompts()]
    assert "product_advisor" in prompt_names
    assert "developer_assistant" in prompt_names
