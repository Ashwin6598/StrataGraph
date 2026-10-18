"""
Tests for Code Domain Owner Email Approval and Ingestion Workflow.
Verifies CODEOWNERS parsing, email dispatch, staging under PENDING_APPROVAL,
and activation/ingestion into the knowledge graph upon email approval.
"""

import pytest
from click.testing import CliRunner
from codegraph.db import db
from codegraph.schema import Relationships
from codegraph.approval_service import (
    resolve_domain_owner,
    send_approval_email,
    approve_bugfix_and_ingest,
    SENT_APPROVAL_EMAILS
)
from codegraph.tools.ingest_tools import record_bugfix, approve_bugfix_via_email
from codegraph.mcp_server import server
from codegraph.__main__ import main


def test_resolve_domain_owner_from_codeowners():
    """Verify code domain owners are resolved according to .github/CODEOWNERS."""
    owner_pay = resolve_domain_owner(
        function_name="validate_card",
        file_path="demo_data/code/payment_service.py"
    )
    assert owner_pay == "payment-domain-owner@payflow.internal"

    owner_fraud = resolve_domain_owner(
        function_name="calculate_risk_score",
        file_path="demo_data/code/fraud_detector.py"
    )
    assert owner_fraud == "fraud-security-owner@payflow.internal"

    owner_refund = resolve_domain_owner(
        function_name="process_refund",
        file_path="demo_data/code/refund_processor.py"
    )
    assert owner_refund == "settlements-owner@payflow.internal"

    # Fallback to wildcard or default
    owner_default = resolve_domain_owner(
        function_name="unknown_func",
        file_path="src/other/module.py"
    )
    assert "@payflow.internal" in owner_default


def test_record_bugfix_dispatches_email_to_domain_owner():
    """Verify unapproved bug fix dispatches email to domain owner and stages with token."""
    initial_email_count = len(SENT_APPROVAL_EMAILS)

    res = record_bugfix(
        ticket_id="BUG-777-EMAIL",
        symptom="Currency precision discrepancy in billing",
        rca="Rounding error in float arithmetic",
        fix_summary="Switched to decimal.Decimal arithmetic",
        affected_function_name="validate_card",
        approved_by_lead=False
    )
    result = res["result"]

    assert result["status"] == "PENDING_APPROVAL"
    assert result["approved"] is False
    assert result["domain_owner"] == "payment-domain-owner@payflow.internal"
    assert result["approval_token"] is not None
    assert result["email_dispatched"] is True

    # Verify email was recorded in outbox
    assert len(SENT_APPROVAL_EMAILS) == initial_email_count + 1
    last_email = SENT_APPROVAL_EMAILS[-1]
    assert last_email["to"] == "payment-domain-owner@payflow.internal"
    assert "BUG-777-EMAIL" in last_email["subject"]
    assert result["approval_token"] in last_email["body_text"]
    assert result["approval_token"] in last_email["approve_url"]

    # Verify staged node in graph
    fix_node = db.memory_graph.nodes.get("fix:BUG-777-EMAIL")
    assert fix_node is not None
    assert fix_node["properties"]["approval_status"] == "PENDING_APPROVAL"
    assert fix_node["properties"]["approval_token"] == result["approval_token"]


def test_approve_bugfix_via_email_success():
    """Verify valid email approval token ingests fix into DB and activates FIXES_FUNCTION edge."""
    # 1. Stage a bugfix
    stage_res = record_bugfix(
        ticket_id="BUG-888-APPROVE",
        symptom="Race condition in ledger balance",
        rca="Missing mutex around balance decrement",
        fix_summary="Added Redis distributed lock",
        affected_function_name="validate_card",
        approved_by_lead=False
    )
    token = stage_res["result"]["approval_token"]

    # 2. Approve via email token
    app_res = approve_bugfix_via_email(
        ticket_id="BUG-888-APPROVE",
        approval_token=token,
        approver_email="payment-domain-owner@payflow.internal"
    )
    result = app_res["result"]

    assert result["status"] == "APPROVED"
    assert result["approved"] is True
    assert result["approved_by"] == "payment-domain-owner@payflow.internal"

    # 3. Check graph state
    fix_node = db.memory_graph.nodes.get("fix:BUG-888-APPROVE")
    assert fix_node["properties"]["approval_status"] == "APPROVED"
    assert fix_node["properties"]["approved_by"] == "payment-domain-owner@payflow.internal"

    # 4. Check edge activation
    edges = [
        e for e in db.memory_graph.edges
        if e["from"] == "fix:BUG-888-APPROVE" and e["rel"] == Relationships.FIXES_FUNCTION
    ]
    assert len(edges) > 0
    assert edges[0]["properties"]["approval_status"] == "APPROVED"


def test_approve_bugfix_via_email_invalid_token():
    """Verify approval is rejected if token does not match."""
    record_bugfix(
        ticket_id="BUG-999-TAMPER",
        symptom="Unchecked buffer allocation",
        rca="Memory buffer overflow",
        fix_summary="Restricted buffer size",
        affected_function_name="validate_card",
        approved_by_lead=False
    )

    app_res = approve_bugfix_via_email(
        ticket_id="BUG-999-TAMPER",
        approval_token="invalid_forged_token_12345"
    )
    assert app_res["result"]["status"] == "REJECTED"

    # Check node remains unapproved
    fix_node = db.memory_graph.nodes.get("fix:BUG-999-TAMPER")
    assert fix_node["properties"]["approval_status"] == "PENDING_APPROVAL"


def test_approve_bugfix_already_approved():
    """Verify re-approving an already approved fix returns ALREADY_APPROVED."""
    res = record_bugfix(
        ticket_id="BUG-1010-DOUBLE",
        symptom="Timeout on third-party webhook",
        rca="Network packet drop",
        fix_summary="Added timeout retry policy",
        affected_function_name="validate_card",
        approved_by_lead=False
    )
    token = res["result"]["approval_token"]

    approve_bugfix_via_email("BUG-1010-DOUBLE", token)
    second_res = approve_bugfix_via_email("BUG-1010-DOUBLE", token)

    assert second_res["result"]["status"] == "ALREADY_APPROVED"


def test_cli_approve_bugfix_command():
    """Verify click CLI 'approve-bugfix' executes approval and displays confirmation."""
    res = record_bugfix(
        ticket_id="BUG-2020-CLI",
        symptom="CLI approval test",
        rca="Synthetic test defect",
        fix_summary="CLI verification",
        affected_function_name="validate_card",
        approved_by_lead=False
    )
    token = res["result"]["approval_token"]

    runner = CliRunner()
    result = runner.invoke(main, [
        "approve-bugfix",
        "--ticket", "BUG-2020-CLI",
        "--token", token,
        "--approver", "lead@payflow.internal"
    ])

    assert result.exit_code == 0
    assert "Ingestion Successful!" in result.output
    assert "BUG-2020-CLI" in result.output


@pytest.mark.anyio
async def test_mcp_approve_bugfix_registered():
    """Verify approve_bugfix_via_email is registered as an MCP tool."""
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert "approve_bugfix_via_email" in tool_names
