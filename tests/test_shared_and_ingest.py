"""
Unit and integration tests for Shared Tools and Ingestion Tools in CodeGraph.
Tests cover graph search, neighborhood expansion, traversal explanations,
file ingestion pipelines, and the human-in-the-loop bugfix approval workflow.
"""

import pytest
from codegraph.db import db
from codegraph.tools.shared_tools import (
    search_graph,
    get_related_entities,
    explain_traversal,
)
from codegraph.tools.ingest_tools import (
    ingest_codebase,
    ingest_prd,
    ingest_adr,
    ingest_runbook,
    record_bugfix,
)


def test_search_graph_unfiltered():
    """Verify full-text search matches properties across multiple entity types."""
    res = search_graph("refund")
    data = res["result"]

    assert data["total_matches"] > 0
    labels = {m["label"] for m in data["matches"]}
    assert len(labels) >= 1


def test_search_graph_filtered():
    """Verify full-text search respects entity_type filtering."""
    res = search_graph("retry", entity_type="Decision")
    data = res["result"]

    assert data["total_matches"] >= 1
    for m in data["matches"]:
        assert m["label"] == "Decision"


def test_search_graph_no_match():
    """Verify search returns empty results cleanly when no matches exist."""
    res = search_graph("extraterrestrial_subspace_frequency")
    data = res["result"]

    assert data["total_matches"] == 0
    assert len(data["matches"]) == 0


def test_get_related_entities_one_hop():
    """Verify 1-hop neighborhood retrieves immediate connected entities."""
    res = get_related_entities("func:retry_with_backoff", hops=1)
    data = res["result"]

    assert data["connected_entities_count"] >= 1
    connected_ids = [e["node_id"] for e in data["connected_entities"]]
    assert any("decision" in cid or "issue" in cid or "req" in cid for cid in connected_ids)


def test_get_related_entities_multi_hop():
    """Verify 2-hop traversal retrieves a wider blast-radius graph."""
    res_1 = get_related_entities("func:retry_with_backoff", hops=1)
    res_2 = get_related_entities("func:retry_with_backoff", hops=2)

    assert res_2["result"]["connected_entities_count"] >= res_1["result"]["connected_entities_count"]


def test_get_related_entities_missing_node():
    """Verify neighborhood query returns structured error for nonexistent node."""
    res = get_related_entities("imaginary_ghost_node_999")
    assert "not found" in res["result"]["error"].lower()


def test_explain_traversal():
    """Verify human-readable ASCII visualization of multi-hop paths."""
    sample_steps = [
        {"from_node": "PRDInput(checkout)", "relationship": "SPECIFIES_REQUIREMENT", "to_node": "REQ-001", "explanation": "Checkout PRD requires card validation"},
        {"from_node": "REQ-001", "relationship": "IMPLEMENTED_BY_FUNCTION", "to_node": "validate_card", "explanation": "Implemented in payment_service.py"},
    ]
    explanation = explain_traversal(sample_steps)

    assert "Graph Traversal Path Visualization" in explanation
    assert "PRDInput(checkout)" in explanation
    assert "validate_card" in explanation
    assert "SPECIFIES_REQUIREMENT" in explanation


def test_ingest_codebase_directory():
    """Verify directory parser processes Python code files into graph nodes."""
    res = ingest_codebase("demo_data/code")

    assert res["status"] == "SUCCESS"
    assert res["files_processed"] >= 3


def test_ingest_prd_and_adr_files():
    """Verify markdown parsers correctly ingest PRD and ADR files."""
    prd_res = ingest_prd("demo_data/prd/payment-gateway-prd.md")
    assert prd_res["status"] == "INGESTED"
    assert prd_res["requirements_ingested"] >= 3

    adr_res = ingest_adr("demo_data/adr/001-fraud-detection-engine.md")
    assert adr_res["status"] == "INGESTED"
    assert "ADR-001" in adr_res["adr_id"]


def test_record_bugfix_approval_workflow_unapproved():
    """Verify human-in-the-loop workflow marks unapproved bug fixes as PENDING_APPROVAL."""
    res = record_bugfix(
        ticket_id="BUG-999-TEST",
        symptom="Simulated memory leak under synthetic test",
        rca="Synthetic test defect",
        fix_summary="Added garbage collection hook",
        affected_function_name="validate_card",
        approved_by_lead=False
    )
    data = res["result"]

    assert data["ticket_id"] == "BUG-999-TEST"
    assert data["status"] == "PENDING_APPROVAL"
    assert data["approved"] is False

    # Check node in graph
    fix_node = db.memory_graph.nodes.get("fix:BUG-999-TEST")
    assert fix_node is not None
    assert fix_node["properties"]["approval_status"] == "PENDING_APPROVAL"


def test_record_bugfix_approval_workflow_approved():
    """Verify human-in-the-loop workflow marks approved bug fixes as APPROVED."""
    res = record_bugfix(
        ticket_id="BUG-1000-TEST",
        symptom="Minor rounding difference on currency conversion",
        rca="Floating point precision issue",
        fix_summary="Used decimal.Decimal representation",
        affected_function_name="validate_card",
        approved_by_lead=True
    )
    data = res["result"]

    assert data["ticket_id"] == "BUG-1000-TEST"
    assert data["status"] == "APPROVED"
    assert data["approved"] is True

    fix_node = db.memory_graph.nodes.get("fix:BUG-1000-TEST")
    assert fix_node is not None
    assert fix_node["properties"]["approval_status"] == "APPROVED"


def test_unified_ingestion_pipeline():
    """Verify unified pipeline processes arbitrary repositories, documents, and auto-links them."""
    from codegraph.ingest.pipeline import IngestionPipeline
    pipeline = IngestionPipeline(project_name="Test Enterprise Service", project_id="project:test_ent")
    res = pipeline.run(
        code_dir="demo_data/code",
        prd_dir="demo_data/prd",
        adr_dir="demo_data/adr",
        runbook_dir="demo_data/runbooks",
        git_repo_path="."
    )

    assert res["status"] == "SUCCESS"
    s = res["summary"]
    assert s["code_files_processed"] >= 3
    assert s["prds_processed"] >= 1
    assert s["adrs_processed"] >= 2
    assert s["cross_links_created"] > 0

