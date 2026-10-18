"""
Unit and integration tests for CodeGraph Command Line Interface (CLI).
Tests CLI commands: status, demo, seed, and help.
"""

import pytest
from click.testing import CliRunner
from codegraph.__main__ import main


def test_cli_help():
    """Verify CLI help text displays available subcommands."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "CodeGraph" in result.output
    assert "serve" in result.output
    assert "status" in result.output
    assert "seed" in result.output
    assert "demo" in result.output


def test_cli_status():
    """Verify 'codegraph status' outputs graph statistics and engine information."""
    runner = CliRunner()
    result = runner.invoke(main, ["status"])

    assert result.exit_code == 0
    assert "CodeGraph Backend Status" in result.output
    assert "Backend Engine" in result.output
    assert "Nodes Indexed" in result.output
    assert "Edges Indexed" in result.output


def test_cli_demo():
    """Verify 'codegraph demo' executes end-to-end product and developer scenarios."""
    runner = CliRunner()
    result = runner.invoke(main, ["demo"])

    assert result.exit_code == 0
    assert "CodeGraph Demonstration" in result.output
    assert "[Product Persona]" in result.output
    assert "[Developer Persona]" in result.output
    assert "REFUND_TIMEOUT" in result.output
    assert "Demo completed with 100% graph explainability" in result.output


def test_cli_seed():
    """Verify 'codegraph seed' re-initializes and seeds the 4-pillar knowledge graph."""
    runner = CliRunner()
    result = runner.invoke(main, ["seed"])

    assert result.exit_code == 0
    assert "Successfully Seeded" in result.output


def test_cli_ingest():
    """Verify 'codegraph ingest' CLI runs unified ingestion on external directories."""
    runner = CliRunner()
    result = runner.invoke(main, [
        "ingest",
        "--project-name", "Test Service",
        "--code", "demo_data/code",
        "--prd", "demo_data/prd",
        "--adr", "demo_data/adr"
    ])

    assert result.exit_code == 0
    assert "Ingestion & Auto-Linking Complete" in result.output
    assert "Code Files Processed" in result.output

