"""
Unit tests for Product Persona MCP tools.
Validates business requirement coverage, scenario simulations, timeline audits, and missing gap detection.
"""

from codegraph.tools.product_tools import (
    query_prd_coverage,
    simulate_scenario,
    get_change_history,
    list_uncovered_requirements,
)


def test_query_prd_coverage():
    """Verify PRD coverage metrics and missing requirement detection."""
    res = query_prd_coverage()
    data = res["result"]

    assert data["total_requirements"] == 9
    assert data["implemented_count"] == 7
    assert data["unimplemented_count"] == 2
    assert "77.8%" in data["coverage_percentage"]

    # Missing requirements check
    missing_ids = [m["id"] for m in data["missing_requirements"]]
    assert "REQ-004" in missing_ids
    assert "REQ-008" in missing_ids

    # Explainability check
    assert "Project" in res["cypher_query"]
    assert len(res["traversal_path"]) > 0


def test_simulate_scenario_expired_card():
    """Verify simulation of expired card scenario."""
    res = simulate_scenario("expired card")
    data = res["result"]

    assert len(data["matched_guardrails"]) > 0
    top = data["matched_guardrails"][0]
    assert "CARD_EXPIRED" in top["violation_code"]
    assert top["handled_in_code"] is True
    assert "validate_card" in top["workflow_components"]
    assert "plain_english_assessment" in data


def test_simulate_scenario_refund_window():
    """Verify simulation of refund settlement window."""
    res = simulate_scenario("30 days refund limit")
    data = res["result"]

    assert len(data["matched_guardrails"]) > 0
    top = data["matched_guardrails"][0]
    assert "REFUND_WINDOW_EXPIRED" in top["violation_code"]


def test_simulate_scenario_unknown_graceful():
    """Verify non-existent business scenario returns a helpful recommendation without crash."""
    res = simulate_scenario("cryptocurrency payment with quantum tokens")
    data = res["result"]

    assert "No direct match was found" in data["plain_english_assessment"]
    assert "Recommendation" in data["plain_english_assessment"]


def test_get_change_history_filtering():
    """Verify timeline change history and date-range filtering."""
    # Full history
    all_res = get_change_history()
    assert all_res["result"]["total_changes"] >= 4

    # Date-filtered history
    filtered = get_change_history(from_date="2026-02-01")
    for r in filtered["result"]["timeline"]:
        assert r["date"] >= "2026-02-01"

    # Verify what and why lineage
    first = all_res["result"]["timeline"][0]
    assert "what_changed" in first
    assert "why_changed" in first


def test_list_uncovered_requirements():
    """Verify list of unstarted requirements."""
    res = list_uncovered_requirements()
    data = res["result"]

    assert data["uncovered_count"] == 2
    ids = {r["id"] for r in data["uncovered_requirements"]}
    assert "REQ-004" in ids
    assert "REQ-008" in ids
