"""
Unit and integration tests for CodeGraph Model Context Protocol (MCP) Server.
Tests tool registration, persona prompt generation, and direct MCP tool dispatch.
"""

import pytest
from codegraph.mcp_server import server


@pytest.mark.anyio
async def test_mcp_server_metadata():
    """Verify MCP server name and core instructions are properly configured."""
    assert server.name == "codegraph"
    assert "Connected Knowledge Graph" in server.instructions
    assert "Product Tools" in server.instructions
    assert "Developer Tools" in server.instructions


@pytest.mark.anyio
async def test_mcp_tool_registry():
    """Verify all 17 persona and operational tools are registered on the MCP server."""
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}

    # Product Persona Tools
    assert "query_prd_coverage" in tool_names
    assert "simulate_scenario" in tool_names
    assert "get_change_history" in tool_names
    assert "list_uncovered_requirements" in tool_names

    # Developer Persona Tools
    assert "debug_issue" in tool_names
    assert "check_safe_to_change" in tool_names
    assert "get_function_lineage" in tool_names
    assert "review_pr_diff" in tool_names
    assert "cross_org_bug_check" in tool_names

    # Shared Tools
    assert "search_graph" in tool_names
    assert "get_related_entities" in tool_names
    assert "explain_traversal" in tool_names

    # Ingestion Tools
    assert "ingest_codebase" in tool_names
    assert "ingest_prd" in tool_names
    assert "ingest_adr" in tool_names
    assert "ingest_runbook" in tool_names
    assert "record_bugfix" in tool_names


@pytest.mark.anyio
async def test_mcp_prompts_registry():
    """Verify both Product Advisor and Developer Assistant personas are registered."""
    prompts = await server.list_prompts()
    prompt_names = {p.name for p in prompts}

    assert "product_advisor" in prompt_names
    assert "developer_assistant" in prompt_names


@pytest.mark.anyio
async def test_mcp_product_advisor_prompt_rules():
    """Verify product advisor prompt enforces plain English, no code, and graph grounding."""
    prompt = await server.get_prompt("product_advisor")
    assert prompt is not None
    # Check messages in prompt
    messages_text = " ".join([m.content.text for m in prompt.messages if hasattr(m.content, "text")])
    assert "Product Advisor" in messages_text
    assert "NEVER output code snippets" in messages_text
    assert "query_prd_coverage" in messages_text


@pytest.mark.anyio
async def test_mcp_developer_assistant_prompt_rules():
    """Verify developer assistant prompt enforces line numbers, ADR constraints, and safety checks."""
    prompt = await server.get_prompt("developer_assistant")
    assert prompt is not None
    messages_text = " ".join([m.content.text for m in prompt.messages if hasattr(m.content, "text")])
    assert "Engineering Assistant" in messages_text
    assert "check_safe_to_change" in messages_text
    assert "ADR" in messages_text


@pytest.mark.anyio
async def test_mcp_call_tool_product():
    """Verify executing a product tool via MCP returns valid content."""
    res = await server.call_tool("simulate_scenario", {"scenario_query": "card expired"})
    assert res is not None
    assert len(res.content) > 0


@pytest.mark.anyio
async def test_mcp_call_tool_developer():
    """Verify executing a developer tool via MCP returns valid content."""
    res = await server.call_tool("check_safe_to_change", {"function_name": "retry_with_backoff"})
    assert res is not None
    assert len(res.content) > 0
