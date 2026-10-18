"""
Tests for Project Entity Dual-Ownership Model (Codebase Owner & PRD Owner).
Validates schema properties, pipeline initialization, CLI commands, and database persistence.
"""

from click.testing import CliRunner
from codegraph.db import db
from codegraph.schema import ProjectNode
from codegraph.ingest.pipeline import IngestionPipeline
from codegraph.__main__ import main


def test_project_node_schema_owners():
    """Verify ProjectNode contains codebase_owner and prd_owner attributes."""
    # Default values
    p_default = ProjectNode(
        id="project:test",
        name="Test Service",
        description="Test service description"
    )
    assert p_default.codebase_owner == "payment-tech-lead@payflow.internal"
    assert p_default.prd_owner == "product-lead@payflow.internal"

    # Custom explicit values
    p_custom = ProjectNode(
        id="project:auth",
        name="Auth Service",
        description="Authentication and SSO service",
        codebase_owner="sec-lead@auth.internal",
        prd_owner="identity-pm@auth.internal"
    )
    assert p_custom.codebase_owner == "sec-lead@auth.internal"
    assert p_custom.prd_owner == "identity-pm@auth.internal"


def test_seeded_project_node_owners():
    """Verify seeded PayFlow project node contains both owners."""
    project_node = db.memory_graph.nodes.get("project:payflow")
    assert project_node is not None
    props = project_node["properties"]
    assert props.get("codebase_owner") == "payment-tech-lead@payflow.internal"
    assert props.get("prd_owner") == "product-lead@payflow.internal"


def test_pipeline_project_owners():
    """Verify IngestionPipeline properly populates owners on the created Project node."""
    pipeline = IngestionPipeline(
        project_name="Custom Ingestion Service",
        project_id="project:custom_ingest",
        codebase_owner="arch-lead@custom.internal",
        prd_owner="platform-pm@custom.internal"
    )

    res = pipeline.run(
        code_dir="demo_data/code",
        max_commits=5
    )

    summary = res["summary"]
    assert summary["codebase_owner"] == "arch-lead@custom.internal"
    assert summary["prd_owner"] == "platform-pm@custom.internal"

    # Verify node in DB
    node = db.memory_graph.nodes.get("project:custom_ingest")
    assert node is not None
    props = node["properties"]
    assert props["codebase_owner"] == "arch-lead@custom.internal"
    assert props["prd_owner"] == "platform-pm@custom.internal"


def test_cli_ingest_with_owners():
    """Verify CLI ingest command accepts --codebase-owner and --prd-owner flags."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "ingest",
        "--project-name", "CLI Project",
        "--project-id", "project:cli_test",
        "--codebase-owner", "cli-dev@payflow.internal",
        "--prd-owner", "cli-pm@payflow.internal",
        "--code", "demo_data/code",
        "--max-commits", "5"
    ])

    assert result.exit_code == 0
    assert "Codebase Owner:       cli-dev@payflow.internal" in result.output
    assert "PRD Owner:            cli-pm@payflow.internal" in result.output


def test_cli_status_displays_owners():
    """Verify CLI status displays Codebase Owner and PRD Owner."""
    runner = CliRunner()
    result = runner.invoke(main, ["status"])

    assert result.exit_code == 0
    assert "Codebase Owner:" in result.output
    assert "PRD Owner:" in result.output
