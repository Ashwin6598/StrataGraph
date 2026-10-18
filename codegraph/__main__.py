"""
CLI Entry Point for CodeGraph.
Supports:
  python -m codegraph serve [--transport stdio|http]
  python -m codegraph seed
  python -m codegraph status
  python -m codegraph demo
"""

import sys
import json
import click
from .config import settings
from .db import db
from .mcp_server import start_server


@click.group()
def main():
    """CodeGraph: Connected Knowledge Graph for Code, PRD, and ADR with Multi-Persona MCP Agents."""
    pass


@main.command()
@click.option("--transport", "-t", default=None, help="Transport mode: stdio, streamable-http, or sse")
@click.option("--port", "-p", default=None, type=int, help="HTTP/SSE server port")
def serve(transport: str, port: int):
    """Start the CodeGraph Model Context Protocol (MCP) server."""
    if transport:
        settings.mcp_transport = transport
    if port:
        settings.mcp_http_port = port
    start_server()


@main.command()
@click.option("--project-name", "-n", default="Enterprise Service", help="Name of the project")
@click.option("--project-id", "-i", default="project:enterprise", help="Unique ID of the project node")
@click.option("--code", "-c", default=None, help="Directory containing source code files")
@click.option("--prd", default=None, help="Directory containing PRD markdown files")
@click.option("--adr", default=None, help="Directory containing ADR markdown files")
@click.option("--runbooks", default=None, help="Directory containing Incident Runbook markdown files")
@click.option("--git", "-g", default=".", help="Path to git repository for commit extraction")
@click.option("--max-commits", default=50, type=int, help="Maximum recent commits to extract")
def ingest(project_name: str, project_id: str, code: str, prd: str, adr: str, runbooks: str, git: str, max_commits: int):
    """Run the unified ingestion pipeline on arbitrary repositories and documents."""
    from .ingest.pipeline import IngestionPipeline
    pipeline = IngestionPipeline(project_name=project_name, project_id=project_id)
    click.echo(f"\n🚀 Running CodeGraph Ingestion Pipeline for '{project_name}'...")
    res = pipeline.run(
        code_dir=code,
        prd_dir=prd,
        adr_dir=adr,
        runbook_dir=runbooks,
        git_repo_path=git,
        max_commits=max_commits
    )
    s = res["summary"]
    stats = res["graph_stats"]
    click.echo("✅ Ingestion & Auto-Linking Complete!")
    click.echo(f"  • Code Files Processed: {s['code_files_processed']}")
    click.echo(f"  • PRD Documents:        {s['prds_processed']}")
    click.echo(f"  • ADR Documents:        {s['adrs_processed']}")
    click.echo(f"  • Runbook Documents:    {s['runbooks_processed']}")
    click.echo(f"  • Commits Ingested:     {s['commits_ingested']}")
    click.echo(f"  • Cross Links Created:  {s['cross_links_created']}")
    click.echo(f"  • Total Graph Nodes:    {stats['nodes']}")
    click.echo(f"  • Total Graph Edges:    {stats['edges']}\n")


@main.command()
def seed():
    """Seed the knowledge graph with the PayFlow demo dataset."""
    from seed import seed_all
    seed_all()



@main.command()
def status():
    """Display connection status, backend engine, and graph statistics."""
    info = db.get_backend_info()
    click.echo("\n📊 CodeGraph Backend Status:")
    click.echo(f"  • Backend Engine:  {info['backend']}")
    click.echo(f"  • Host / Endpoint: {info['host']}")
    click.echo(f"  • Port:            {info['port']}")
    click.echo(f"  • Graph Namespace: {info['graph_name']}")
    click.echo(f"  • Nodes Indexed:   {info['node_count']}")
    click.echo(f"  • Edges Indexed:   {info['edge_count']}")
    click.echo(f"  • MCP Transport:   {settings.mcp_transport}\n")


@main.command()
def demo():
    """Run an automated demonstration of Product and Developer scenarios."""
    from .tools.product_tools import query_prd_coverage, simulate_scenario, get_change_history
    from .tools.developer_tools import debug_issue, check_safe_to_change

    click.echo("\n========================================================")
    click.echo("🎬 CodeGraph Demonstration: Connected Data in Action")
    click.echo("========================================================\n")

    # Product Scenario 1
    click.echo("--- [Product Persona] Scenario 1: How complete is the code vs PRD? ---")
    cov = query_prd_coverage()
    click.echo(cov["result"]["summary"])
    click.echo(f"Cypher Query Executed:\n  {cov['cypher_query']}\n")

    # Product Scenario 2
    click.echo("--- [Product Persona] Scenario 2: What happens if user pays with expired card? ---")
    sim = simulate_scenario("expired card")
    click.echo(sim["result"]["plain_english_assessment"])
    click.echo(f"Cypher Query Executed:\n  {sim['cypher_query']}\n")

    # Developer Scenario 1
    click.echo("--- [Developer Persona] Scenario 3: Debug production error REFUND_TIMEOUT ---")
    dbg = debug_issue("REFUND_TIMEOUT")
    click.echo(dbg["result"]["technical_diagnostic_summary"])
    click.echo(f"Cypher Query Executed:\n  {dbg['cypher_query']}\n")

    # Developer Scenario 2
    click.echo("--- [Developer Persona] Scenario 4: Is it safe to change retry logic in fraud_detector.py? ---")
    safe = check_safe_to_change("retry_with_backoff")
    click.echo(safe["result"]["recommendation"])
    click.echo(f"Cypher Query Executed:\n  {safe['cypher_query']}\n")

    click.echo("========================================================")
    click.echo("✅ Demo completed with 100% graph explainability!")
    click.echo("========================================================\n")


if __name__ == "__main__":
    main()
