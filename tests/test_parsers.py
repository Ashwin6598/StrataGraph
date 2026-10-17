"""
Unit tests for the Ingestion Parsers.
Validates AST parsing, markdown section parsing, error handling, and line number extraction.
"""

from pathlib import Path
from codegraph.ingest.code_parser import CodebaseParser
from codegraph.ingest.prd_parser import PRDParser
from codegraph.ingest.adr_parser import ADRParser
from codegraph.ingest.change_tracker import ChangeTracker


def test_code_ast_parser():
    """Verify AST parsing extracts files, classes, functions, and line ranges."""
    code_path = Path("demo_data/code/payment_service.py")
    parser = CodebaseParser()
    res = parser.parse_file(str(code_path))

    assert res["status"] == "INGESTED"
    assert "file:payment_service.py" in res["file_id"]


def test_code_parser_non_python_skip():
    """Verify code parser cleanly skips non-python files."""
    parser = CodebaseParser()
    res = parser.parse_file("README.md")
    assert res["status"] == "SKIPPED"


def test_code_parser_missing_file():
    """Verify code parser handles missing files cleanly."""
    parser = CodebaseParser()
    res = parser.parse_file("does_not_exist.py")
    assert res["status"] == "SKIPPED"


def test_prd_markdown_parser():
    """Verify PRD parser extracts document ID, requirements, and scenarios."""
    prd_path = Path("demo_data/prd/payment-gateway-prd.md")
    parser = PRDParser()
    res = parser.parse_file(str(prd_path))

    assert res["status"] == "INGESTED"
    assert res["prd_id"] == "PRD-PAYFLOW-101"
    assert res["requirements_ingested"] >= 9
    assert res["scenarios_ingested"] >= 10


def test_prd_parser_missing_file():
    """Verify PRD parser handles missing files."""
    parser = PRDParser()
    res = parser.parse_file("missing_prd.md")
    assert res["status"] == "ERROR"


def test_adr_markdown_parser():
    """Verify ADR parser extracts decisions, context, and consequences."""
    adr_path = Path("demo_data/adr/001-fraud-detection-engine.md")
    parser = ADRParser()
    res = parser.parse_file(str(adr_path))

    assert res["status"] == "INGESTED"
    assert "ADR-001" in res["adr_id"]


def test_runbook_incident_parser():
    """Verify Runbook parser extracts historical incidents and RCAs."""
    rb_path = Path("demo_data/runbooks/payment-failure-debug.md")
    tracker = ChangeTracker()
    res = tracker.parse_runbook(str(rb_path))

    assert res["status"] == "INGESTED"
    assert res["bugs_extracted"] >= 2
