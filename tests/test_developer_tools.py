"""
Unit and integration tests for Developer Persona tools in CodeGraph.
Tests cover root cause analysis (RCA), safety audits, lineage tracing,
PR diff reviews, and cross-organizational incident lookups.
"""

import pytest
from codegraph.tools.developer_tools import (
    debug_issue,
    check_safe_to_change,
    get_function_lineage,
    review_pr_diff,
    cross_org_bug_check,
)


def test_debug_issue_matching():
    """Verify log diagnostics identifies historical incidents, RCA, and verified remediation."""
    res = debug_issue("REFUND_TIMEOUT HTTP 504 on queue consumer")
    data = res["result"]

    assert len(data["matched_incidents"]) > 0
    top = data["matched_incidents"][0]
    assert top["ticket_id"] == "BUG-342"
    assert "concurrency" in top["root_cause_analysis"].lower()
    assert "ADR-002" in str(top["violated_adr"])
    assert "restore" in top["action_taken"].lower()
    assert "BUG-342" in data["technical_diagnostic_summary"]


def test_debug_issue_no_match():
    """Verify unfamiliar error logs return actionable diagnostic advice without crashing."""
    res = debug_issue("QuantumCosmicRayMemoryBitFlipError in reactor")
    data = res["result"]

    assert len(data["matched_incidents"]) == 0
    assert "No direct historical Issue match found" in data["technical_diagnostic_summary"]


def test_check_safe_to_change_constrained():
    """Verify functions governed by ADRs and past regressions are flagged as UNSAFE to change freely."""
    res = check_safe_to_change("retry_with_backoff")
    data = res["result"]

    assert data["safe_to_modify"] is False
    assert "UNSAFE" in data["safety_verdict"]
    assert any("ADR-001" in adr for adr in data["governing_adrs"])
    assert any("BUG-112" in iss for iss in data["past_issues"])
    assert len(data["warnings"]) >= 2


def test_check_safe_to_change_unconstrained():
    """Verify functions without governing ADRs or regression history report SAFE TO MODIFY."""
    res = check_safe_to_change("send_webhook")
    data = res["result"]

    assert data["safe_to_modify"] is True
    assert "SAFE TO MODIFY" in data["safety_verdict"]
    assert len(data["warnings"]) == 0


def test_check_safe_to_change_missing_function():
    """Verify querying an unknown function name returns a clear error status."""
    res = check_safe_to_change("unknown_nonexistent_function")
    data = res["result"]

    assert data["safe"] is False
    assert "not found in knowledge graph" in data["error"]


def test_get_function_lineage():
    """Verify 4-pillar lineage tracing across PRD, ADR, Code, and Historical Commits."""
    res = get_function_lineage("retry_with_backoff")
    data = res["result"]

    assert data["function"] == "retry_with_backoff"
    assert any("ADR-001" in adr for adr in data["governing_adrs"])
    assert any("REQ-010" in r or "Retry" in r for r in data["linked_prd_requirements"])
    assert len(data["timeline_history"]) >= 1

    top_commit = data["timeline_history"][0]
    assert "commit_hash" in top_commit
    assert "what_changed" in top_commit
    assert "why_changed" in top_commit


def test_review_pr_diff_with_violations():
    """Verify PR diff touching constrained functions flags blocking violations."""
    res = review_pr_diff(["retry_with_backoff", "queue_refund_job"])
    data = res["result"]

    assert data["blocking_risk"] is True
    assert "REQUEST_CHANGES" in data["pr_verdict"]

    audits = data["modified_function_audits"]
    assert len(audits) == 2
    assert all(a["status"] == "CONSTRAINED" for a in audits)


def test_review_pr_diff_all_safe():
    """Verify PR diff touching only unconstrained functions is approved."""
    res = review_pr_diff(["send_webhook"])
    data = res["result"]

    assert data["blocking_risk"] is False
    assert "APPROVE" in data["pr_verdict"]
    assert data["modified_function_audits"][0]["status"] == "APPROVED"


def test_cross_org_bug_check_match():
    """Verify cross-org search retrieves past incidents matching symptom pattern."""
    res = cross_org_bug_check("packet loss")
    data = res["result"]

    assert data["found_matches_count"] >= 1
    tickets = [iss["ticket"] for iss in data["historical_issues"]]
    assert "BUG-112" in tickets


def test_cross_org_bug_check_no_match():
    """Verify cross-org search returns zero matches without failure when no pattern matches."""
    res = cross_org_bug_check("unprecedented teleportation failure")
    data = res["result"]

    assert data["found_matches_count"] == 0
    assert len(data["historical_issues"]) == 0
