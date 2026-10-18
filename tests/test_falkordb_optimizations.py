"""
Unit tests for FalkorDB GraphBLAS performance optimizations.
Verifies compliance with:
- Rule 2: String Interning (intern() on high-cardinality/repeated string properties)
- Rule 3: Explicit Indexing (CREATE INDEX FOR (label) ON (property) for core entities)
- Rule 4: Isolation (Logical graph key partitioning per project/tenant)
- Rule 5: Explicit Labels (Targeted label matrices; no open MATCH (a))
- Rule 7: Parameterization (Query caching via parameterized Cypher)
"""

import pytest
from unittest.mock import MagicMock
from codegraph.db import db, CORE_INDEXES, INTERNED_FIELDS, GraphDatabase


class TestFalkorDBOptimizations:
    """Tests for GraphBLAS performance optimization features."""

    def test_rule_3_ensure_indexes_generates_all_core_indexes(self):
        indexes = db.ensure_indexes()
        assert len(indexes) == len(CORE_INDEXES)
        # Check specific key entities have explicit indexes
        assert "CREATE INDEX FOR (n:Project) ON (n.id)" in indexes
        assert "CREATE INDEX FOR (n:Function) ON (n.id)" in indexes
        assert "CREATE INDEX FOR (n:Function) ON (n.name)" in indexes
        assert "CREATE INDEX FOR (n:FunctionalRequirement) ON (n.id)" in indexes
        assert "CREATE INDEX FOR (n:Decision) ON (n.id)" in indexes
        assert "CREATE INDEX FOR (n:Story) ON (n.key)" in indexes

    def test_rule_4_graph_isolation_keys(self):
        key = db.get_project_graph_key("project:payflow")
        assert key.endswith("_payflow")
        assert "project:" not in key

        # Select graph key updates active graph
        db.select_graph(key)
        assert db.active_graph_name == key
        info = db.get_backend_info()
        assert info["graph_name"] == key
        # Reset back
        db.select_graph("codegraph_demo")

    def test_rule_5_resolve_label_deterministic(self):
        assert db.resolve_label("project:payflow") == "Project"
        assert db.resolve_label("func:authorize_payment") == "Function"
        assert db.resolve_label("req:REQ-001") == "FunctionalRequirement"
        assert db.resolve_label("dec:ADR-001") == "Decision"
        assert db.resolve_label("epic:EPIC-PAY-CORE") == "Epic"
        assert db.resolve_label("feat:FEAT-001") == "AgileFeature"
        assert db.resolve_label("story:PAY-101") == "Story"

    def test_rule_2_and_7_create_node_string_interning_and_parameterization(self):
        mock_graph = MagicMock()
        mock_client = MagicMock()
        mock_client.select_graph.return_value = mock_graph

        test_db = GraphDatabase()
        test_db.is_falkordb = True
        test_db.falkor_graph = mock_graph
        test_db.falkor_graphs["test_graph"] = mock_graph

        props = {
            "title": "Card Payment Auth",
            "status": "IMPLEMENTED",
            "priority": "CRITICAL"
        }
        test_db.create_node("req:REQ-001", "FunctionalRequirement", props, graph_name="test_graph")

        assert mock_graph.query.called
        call_args = mock_graph.query.call_args
        cypher = call_args[0][0]
        params = call_args[0][1]

        # Verify String Interning (Rule 2)
        assert "intern($status)" in cypher
        assert "intern($priority)" in cypher
        # Verify Parameterization (Rule 7)
        assert params["id"] == "req:REQ-001"
        assert params["status"] == "IMPLEMENTED"
        assert params["priority"] == "CRITICAL"
        assert params["props"]["title"] == "Card Payment Auth"

    def test_rule_5_and_7_create_edge_explicit_labels_and_parameterization(self):
        mock_graph = MagicMock()
        test_db = GraphDatabase()
        test_db.is_falkordb = True
        test_db.falkor_graph = mock_graph
        test_db.falkor_graphs["test_graph"] = mock_graph

        test_db.create_edge(
            from_id="project:payflow",
            rel_type="HAS_EPIC",
            to_id="epic:EPIC-PAY-CORE",
            properties={"created_at": "2026-10-18"},
            graph_name="test_graph"
        )

        assert mock_graph.query.called
        call_args = mock_graph.query.call_args
        cypher = call_args[0][0]
        params = call_args[0][1]

        # Verify Explicit Labels (Rule 5) - No open MATCH (a)
        assert "MATCH (a:Project {id: $from_id}), (b:Epic {id: $to_id})" in cypher
        # Verify Parameterization (Rule 7)
        assert params["from_id"] == "project:payflow"
        assert params["to_id"] == "epic:EPIC-PAY-CORE"
        assert params["props"]["created_at"] == "2026-10-18"
