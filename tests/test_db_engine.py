"""
Unit tests for the Database layer and LocalMemoryGraph engine.
Validates persistence, neighbor traversal, fallback mechanisms, and graph idempotency.
"""

import os
import tempfile
import pytest
from codegraph.db import LocalMemoryGraph, GraphDatabase


def test_local_memory_graph_crud():
    """Verify in-memory node and edge CRUD operations."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        graph = LocalMemoryGraph(persist_file=tmp_path)
        graph.clear()

        # Add nodes
        graph.add_node("node:1", "Project", {"name": "Test Project"})
        graph.add_node("node:2", "Function", {"name": "test_func"})

        assert len(graph.nodes) == 2
        assert graph.nodes["node:1"]["properties"]["name"] == "Test Project"

        # Add directed edge
        graph.add_edge("node:1", "CONTAINS", "node:2", {"weight": 1.0})
        assert len(graph.edges) == 1

        # Test neighbor queries
        out_neighbors = graph.get_neighbors("node:1", direction="out")
        assert len(out_neighbors) == 1
        assert out_neighbors[0]["target_id"] == "node:2"
        assert out_neighbors[0]["relationship"] == "CONTAINS"

        in_neighbors = graph.get_neighbors("node:2", direction="in")
        assert len(in_neighbors) == 1
        assert in_neighbors[0]["target_id"] == "node:1"

        both_neighbors = graph.get_neighbors("node:1", direction="both")
        assert len(both_neighbors) == 1

        # Persistence test
        graph.save()
        assert os.path.exists(tmp_path)

        # Reload into new instance
        new_graph = LocalMemoryGraph(persist_file=tmp_path)
        assert len(new_graph.nodes) == 2
        assert len(new_graph.edges) == 1
        assert new_graph.nodes["node:2"]["properties"]["name"] == "test_func"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_graph_database_backend_status():
    """Verify backend info report from GraphDatabase wrapper."""
    db_instance = GraphDatabase()
    info = db_instance.get_backend_info()

    assert "backend" in info
    assert "host" in info
    assert "port" in info
    assert "graph_name" in info
    assert "node_count" in info
    assert "edge_count" in info


def test_neighbor_traversal_on_missing_node():
    """Verify that neighbor traversal on a non-existent node returns empty list without error."""
    graph = LocalMemoryGraph()
    neighbors = graph.get_neighbors("node:does_not_exist")
    assert neighbors == []
