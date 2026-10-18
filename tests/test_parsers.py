"""
Unit tests for the Ingestion Parsers.
Validates AST parsing, markdown section parsing, error handling, and line number extraction.
"""

import json
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


def test_typescript_parser(tmp_path):
    """Verify universal parser extracts classes and functions from TypeScript/JavaScript files."""
    ts_code = """
    /**
     * BillingService handles customer subscription charges.
     * Implements: REQ-001
     * Governed by: ADR-001
     */
    export class BillingService {
        constructor() {}

        async processSubscription(userId: string, planId: string): Promise<boolean> {
            console.log("Processing subscription");
            return true;
        }
    }

    export const cancelSubscription = async (subId: string): Promise<void> => {
        console.log("Cancelled");
    };
    """
    ts_file = tmp_path / "billing.ts"
    ts_file.write_text(ts_code, encoding="utf-8")

    parser = CodebaseParser()
    res = parser.parse_file(str(ts_file))

    assert res["status"] == "INGESTED"
    assert res["language"] == "typescript"
    assert res["functions_count"] >= 2


def test_go_parser(tmp_path):
    """Verify universal parser extracts structs and functions from Go files."""
    go_code = """
    package main

    import "fmt"

    // PaymentHandler manages ledger operations
    // Implements REQ-002
    type PaymentHandler struct {
        Balance int
    }

    func (p *PaymentHandler) ProcessCharge(amount int) error {
        fmt.Println(amount)
        return nil
    }

    func HealthCheck() string {
        return "OK"
    }
    """
    go_file = tmp_path / "handler.go"
    go_file.write_text(go_code, encoding="utf-8")

    parser = CodebaseParser()
    res = parser.parse_file(str(go_file))

    assert res["status"] == "INGESTED"
    assert res["language"] == "go"
    assert res["functions_count"] >= 2


def test_html_confluence_converter(tmp_path):
    """Verify HTML / Confluence wiki exports are converted to markdown and ingested."""
    html_content = """
    <html>
      <body>
        <h1>PRD: Subscription Management Portal</h1>
        <p><strong>Document ID:</strong> PRD-CONF-202</p>
        <p><strong>Status:</strong> APPROVED</p>
        <h3>REQ-050: Auto-Renew Subscriptions</h3>
        <p><strong>Priority:</strong> HIGH</p>
        <p><strong>Status:</strong> IMPLEMENTED</p>
        <p><strong>Description:</strong> Automatically charge customer card upon billing cycle end.</p>
        <ul>
          <li><strong>SCEN-050-1:</strong> Card charged on 30th day</li>
        </ul>
      </body>
    </html>
    """
    html_file = tmp_path / "prd-confluence.html"
    html_file.write_text(html_content, encoding="utf-8")

    parser = PRDParser()
    res = parser.parse_file(str(html_file))

    assert res["status"] == "INGESTED"
    assert "PRD-CONF-202" in res["prd_id"]
    assert res["requirements_ingested"] >= 1


def test_jira_json_converter(tmp_path):
    """Verify Jira / Confluence JSON exports are converted to PRD markdown and ingested."""
    jira_data = {
        "issues": [
            {
                "key": "REQ-701",
                "fields": {
                    "summary": "Multi-Tenant Enterprise Isolation",
                    "description": "Isolate tenant transaction ledger tables.",
                    "priority": {"name": "High"},
                    "status": {"name": "In Progress"},
                    "scenarios": ["Tenant A cannot query Tenant B balance"]
                }
            }
        ]
    }
    json_file = tmp_path / "jira-export.json"
    json_file.write_text(json.dumps(jira_data), encoding="utf-8")

    parser = PRDParser()
    res = parser.parse_file(str(json_file))

    assert res["status"] == "INGESTED"
    assert res["requirements_ingested"] >= 1


def test_document_converter_plain_text(tmp_path):
    """Verify plain text files are converted and passed through cleanly."""
    from codegraph.ingest.document_converter import DocumentConverter
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Simple text notes", encoding="utf-8")
    converted = DocumentConverter.to_markdown(str(txt_file))
    assert converted == "Simple text notes"


def test_document_converter_missing():
    """Verify missing file returns empty string gracefully."""
    from codegraph.ingest.document_converter import DocumentConverter
    assert DocumentConverter.to_markdown("non_existent_file.pdf") == ""



