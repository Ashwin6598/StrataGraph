"""
Unit and integration tests for Program Manager Persona Tools, Jira Ingestion,
and 5-Pillar Agile Execution Lineage.
"""

import pytest
from seed import seed_all
from codegraph.db import db
from codegraph.ingest.jira_parser import JiraBoardParser
from codegraph.ingest.pipeline import IngestionPipeline
from codegraph.tools.program_tools import (
    query_program_delivery_status,
    diagnose_delivery_bottlenecks,
    get_feature_lead_time_metrics,
    trace_requirement_to_delivery_chain,
    ingest_jira_board,
)
from codegraph.mcp_server import server


@pytest.fixture(scope="module", autouse=True)
def setup_program_graph():
    """Ensure graph has complete 5-pillar seed data before running tests."""
    seed_all()
    yield
    seed_all()


def test_query_program_delivery_status_seeded():
    res = query_program_delivery_status(project_id="project:payflow")
    data = res["result"]

    assert data["project_id"] == "project:payflow"
    assert data["delivery_progress_percentage"] == 69.0
    assert data["total_story_points"] == 42
    assert data["completed_story_points"] == 29
    assert data["total_epics"] == 3
    assert data["total_features"] == 5
    assert data["total_stories"] == 8
    assert data["blocked_stories_count"] == 1

    blocked = data["blocked_stories"][0]
    assert blocked["key"] == "PAY-307"
    assert "legal and accounting clearance" in blocked["reason"].lower()

    assert "MATCH" in res["cypher_query"]
    assert len(res["traversal_path"]) == 3
    assert "69.0%" in res["explanation"]


def test_diagnose_delivery_bottlenecks():
    res = diagnose_delivery_bottlenecks(project_id="project:payflow")
    data = res["result"]

    assert data["total_bottlenecks_detected"] == 2
    assert len(data["active_blockers"]) == 1
    assert data["active_blockers"][0]["story_key"] == "PAY-307"
    assert data["active_blockers"][0]["requirement_id"] == "req:REQ-008"

    assert len(data["definition_gaps"]) == 1
    assert data["definition_gaps"][0]["requirement_id"] == "req:REQ-004"
    assert len(data["ghost_deliveries"]) == 0

    assert "🚨 Active Dependency Blockers" in res["explanation"]
    assert "⏳ Definition & Backlog Gaps" in res["explanation"]


def test_get_feature_lead_time_metrics():
    res = get_feature_lead_time_metrics(project_id="project:payflow")
    data = res["result"]

    assert data["project_id"] == "project:payflow"
    assert data["overall_average_cycle_time_days"] > 0
    assert data["features_analyzed"] >= 5

    breakdown = {f["feature_key"]: f for f in data["feature_breakdown"]}
    assert "PAY-FEAT-201" in breakdown
    assert breakdown["PAY-FEAT-201"]["completed_stories_count"] == 3
    assert breakdown["PAY-FEAT-201"]["average_cycle_time_days"] is not None

    assert "Fastest turnaround" in res["explanation"] or "Delivery Velocity Metrics" in res["explanation"]


def test_trace_requirement_to_delivery_chain_req_003():
    res = trace_requirement_to_delivery_chain(req_id_or_ticket="REQ-003")
    data = res["result"]

    assert data["prd_requirement"]["id"] == "req:REQ-003"
    assert "Fraud" in data["prd_requirement"]["title"]

    assert data["agile_execution"]["story"] == "PAY-303"
    assert data["agile_execution"]["assignee"] == "Bob Martinez (Tech Lead)"
    assert data["agile_execution"]["story_status"] == "DONE"
    assert not data["agile_execution"]["blocked"]

    assert len(data["governing_adr_decisions"]) >= 1
    assert any("ADR-001" in str(d.get("adr_id")) for d in data["governing_adr_decisions"])

    assert len(data["implementing_code_functions"]) >= 1
    assert any(fn["name"] in ("retry_with_backoff", "assess_risk") for fn in data["implementing_code_functions"])

    assert len(data["operational_regressions"]) >= 1
    assert data["operational_regressions"][0]["ticket"] == "BUG-112"

    assert "5-Pillar Lineage" in res["explanation"]


def test_trace_requirement_to_delivery_chain_blocked_story():
    res = trace_requirement_to_delivery_chain(req_id_or_ticket="PAY-307")
    data = res["result"]

    assert data["agile_execution"]["story"] == "PAY-307"
    assert data["agile_execution"]["blocked"] is True
    assert "legal and accounting clearance" in data["agile_execution"]["blocker_reason"].lower()
    assert data["prd_requirement"]["id"] == "req:REQ-008"


def test_jira_parser_standalone():
    parser = JiraBoardParser(project_id="project:test")
    res = parser.parse_file("demo_data/jira/jira_board_export.json")

    assert len(res["epics"]) == 3
    assert len(res["features"]) == 5
    assert len(res["stories"]) == 8
    assert len(res["edges"]) >= 20

    epic_keys = [e.key for e in res["epics"]]
    assert "PAY-EPIC-101" in epic_keys
    assert "PAY-EPIC-102" in epic_keys
    assert "PAY-EPIC-103" in epic_keys

    story_keys = [s.key for s in res["stories"]]
    assert "PAY-301" in story_keys
    assert "PAY-307" in story_keys


def test_pipeline_with_jira_ingest(tmp_path):
    pipeline = IngestionPipeline(
        project_name="Test Jira Integration",
        project_id="project:pipeline_jira_test"
    )
    result = pipeline.run(
        jira_file="demo_data/jira/jira_board_export.json",
        max_commits=5
    )
    assert result["status"] == "SUCCESS"
    s = result["summary"]
    assert s["jira_epics_processed"] == 3
    assert s["jira_features_processed"] == 5
    assert s["jira_stories_processed"] == 8


@pytest.mark.anyio
async def test_mcp_server_program_tools_and_prompt():
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert "query_program_delivery_status" in tool_names
    assert "diagnose_delivery_bottlenecks" in tool_names
    assert "get_feature_lead_time_metrics" in tool_names
    assert "trace_requirement_to_delivery_chain" in tool_names
    assert "ingest_jira_board" in tool_names

    prompts = await server.list_prompts()
    prompt_names = [p.name for p in prompts]
    assert "program_manager" in prompt_names
    assert "product_advisor" in prompt_names
    assert "developer_assistant" in prompt_names
