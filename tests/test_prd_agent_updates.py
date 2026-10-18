"""
Tests for Agent-Driven PRD Updates and PRD Owner Approval Workflow.
Verifies that agents can propose new features and scenarios,
that proposals are staged under PENDING_APPROVAL and emailed to the project's PRD Owner,
and that valid approval tokens permanently ingest them into the knowledge graph.
"""

import pytest
from click.testing import CliRunner
from codegraph.db import db
from codegraph.schema import Relationships
from codegraph.approval_service import SENT_APPROVAL_EMAILS
from codegraph.tools.product_tools import (
    update_prd_features_and_scenarios,
    approve_prd_update_via_email,
    query_prd_coverage
)
from codegraph.mcp_server import server
from codegraph.__main__ import main


@pytest.fixture(scope="module", autouse=True)
def restore_seed_after_module():
    yield
    from seed import seed_all
    seed_all()



def test_update_prd_features_and_scenarios_staged_unapproved():
    """Verify agent PRD proposal is staged under PENDING_APPROVAL and emailed to PRD owner."""
    initial_email_count = len(SENT_APPROVAL_EMAILS)

    # Initial coverage before proposal
    initial_cov = query_prd_coverage("project:payflow")
    initial_total_reqs = initial_cov["result"]["total_requirements"]

    res = update_prd_features_and_scenarios(
        feature_id="REQ-055",
        feature_title="One-Click Instant Checkout",
        description="Allow authenticated users to checkout in a single click using saved vaulted cards.",
        project_id="project:payflow",
        priority="HIGH",
        scenarios=[
            "Customer clicks Instant Pay and authorization completes in <1s",
            "Customer with expired vaulted card is prompted for CVV"
        ],
        guardrails=[
            "Instant checkout disabled for single orders exceeding $2,000"
        ],
        approved_by_prd_owner=False
    )
    result = res["result"]

    assert result["status"] == "PENDING_APPROVAL"
    assert result["approved"] is False
    assert result["prd_owner"] == "product-lead@payflow.internal"
    assert result["approval_token"] is not None
    assert result["email_dispatched"] is True
    assert result["scenarios_count"] == 2
    assert result["guardrails_count"] == 1

    # Verify requirement and scenarios in graph are marked PENDING_APPROVAL
    req_node = db.memory_graph.nodes.get("req:REQ-055")
    assert req_node is not None
    assert req_node["properties"]["status"] == "PENDING_APPROVAL"

    scen_node = db.memory_graph.nodes.get("scen:REQ-055-1")
    assert scen_node is not None
    assert scen_node["properties"]["status"] == "PENDING_APPROVAL"

    # Verify query_prd_coverage does NOT count pending requirement
    mid_cov = query_prd_coverage("project:payflow")
    assert mid_cov["result"]["total_requirements"] == initial_total_reqs

    # Verify email was captured in outbox
    assert len(SENT_APPROVAL_EMAILS) == initial_email_count + 1
    email = SENT_APPROVAL_EMAILS[-1]
    assert email["to"] == "product-lead@payflow.internal"
    assert "REQ-055" in email["subject"]
    assert result["approval_token"] in email["body_text"]
    assert "One-Click Instant Checkout" in email["body_text"]


def test_approve_prd_update_via_email_success():
    """Verify PRD owner approval token activates feature and scenarios in the graph."""
    # 1. Propose feature
    res = update_prd_features_and_scenarios(
        feature_id="REQ-077",
        feature_title="Crypto Settlement Gateway",
        description="Support USDC and BTC settlements directly into merchant accounts.",
        project_id="project:payflow",
        priority="MEDIUM",
        scenarios=["Merchant receives USDC settlement in 10 minutes"],
        approved_by_prd_owner=False
    )
    token = res["result"]["approval_token"]

    # 2. Approve via email token
    app_res = approve_prd_update_via_email(
        feature_id="REQ-077",
        approval_token=token,
        approver_email="product-lead@payflow.internal"
    )
    result = app_res["result"]

    assert result["status"] == "APPROVED"
    assert result["approved"] is True
    assert result["approved_by"] == "product-lead@payflow.internal"

    # 3. Verify node and edge updated in DB
    req_node = db.memory_graph.nodes.get("req:REQ-077")
    assert req_node["properties"]["status"] == "APPROVED"
    assert req_node["properties"]["approved_by"] == "product-lead@payflow.internal"

    # 4. Verify query_prd_coverage now includes the approved requirement
    post_cov = query_prd_coverage("project:payflow")
    matching = [r for r in post_cov["result"]["missing_requirements"] if r["id"] == "REQ-077"]
    assert len(matching) == 1



def test_approve_prd_update_invalid_token():
    """Verify invalid approval token is rejected."""
    update_prd_features_and_scenarios(
        feature_id="REQ-088",
        feature_title="Unauthorized Proposal",
        description="Test forged token",
        approved_by_prd_owner=False
    )

    app_res = approve_prd_update_via_email(
        feature_id="REQ-088",
        approval_token="forged_bad_token"
    )
    assert app_res["result"]["status"] == "REJECTED"

    req_node = db.memory_graph.nodes.get("req:REQ-088")
    assert req_node["properties"]["status"] == "PENDING_APPROVAL"


def test_update_prd_pre_approved():
    """Verify passing approved_by_prd_owner=True ingests immediately without email gate."""
    res = update_prd_features_and_scenarios(
        feature_id="REQ-099-DIRECT",
        feature_title="Direct Ingest Feature",
        description="Pre-approved administrative update",
        scenarios=["Direct scenario 1"],
        approved_by_prd_owner=True
    )
    assert res["result"]["status"] == "APPROVED"
    assert res["result"]["approved"] is True

    req_node = db.memory_graph.nodes.get("req:REQ-099-DIRECT")
    assert req_node["properties"]["status"] == "APPROVED"


def test_cli_approve_prd_command():
    """Verify click CLI 'approve-prd' successfully processes PRD approval."""
    res = update_prd_features_and_scenarios(
        feature_id="REQ-101-CLI",
        feature_title="CLI PRD Test",
        description="Testing CLI approval",
        approved_by_prd_owner=False
    )
    token = res["result"]["approval_token"]

    runner = CliRunner()
    cli_result = runner.invoke(main, [
        "approve-prd",
        "--feature-id", "REQ-101-CLI",
        "--token", token,
        "--approver", "product-lead@payflow.internal"
    ])

    assert cli_result.exit_code == 0
    assert "Ingestion Successful!" in cli_result.output
    assert "REQ-101-CLI" in cli_result.output


@pytest.mark.anyio
async def test_mcp_prd_tools_registered():
    """Verify update_prd_features_and_scenarios and approve_prd_update_via_email are registered in MCP."""
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert "update_prd_features_and_scenarios" in tool_names
    assert "approve_prd_update_via_email" in tool_names
