"""
Database driver for CodeGraph.
Supports FalkorDB (via OpenCypher) and seamless in-memory fallback with JSON persistence for offline/local demos.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .config import settings

logger = logging.getLogger("codegraph.db")


class LocalMemoryGraph:
    """
    Lightweight, deterministic property graph engine for local development & fallback.
    Maintains nodes and typed directed edges, persisting to JSON.
    """
    def __init__(self, persist_file: Optional[str] = None):
        self.persist_file = persist_file or settings.persist_file
        self.nodes: Dict[str, Dict[str, Any]] = {}  # id -> {label, properties}
        self.edges: List[Dict[str, Any]] = []  # list of {from, rel, to, properties}
        self.load()

    def clear(self):
        self.nodes.clear()
        self.edges.clear()
        if os.path.exists(self.persist_file):
            try:
                os.remove(self.persist_file)
            except OSError:
                pass

    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]):
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": properties
        }

    def add_edge(self, from_id: str, rel_type: str, to_id: str, properties: Optional[Dict[str, Any]] = None):
        self.edges.append({
            "from": from_id,
            "rel": rel_type,
            "to": to_id,
            "properties": properties or {}
        })

    def save(self):
        try:
            data = {
                "nodes": self.nodes,
                "edges": self.edges
            }
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist local graph to {self.persist_file}: {e}")

    def load(self):
        if os.path.exists(self.persist_file):
            try:
                with open(self.persist_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nodes = data.get("nodes", {})
                    self.edges = data.get("edges", [])
            except Exception as e:
                logger.warning(f"Failed to load graph from {self.persist_file}: {e}")

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        neighbors = []
        for e in self.edges:
            if direction in ("out", "both") and e["from"] == node_id:
                target_node = self.nodes.get(e["to"])
                neighbors.append({
                    "relationship": e["rel"],
                    "direction": "OUT",
                    "target_id": e["to"],
                    "target_node": target_node,
                    "node": target_node.get("properties", {}) if target_node else {},
                    "properties": e["properties"]
                })
            elif direction in ("in", "both") and e["to"] == node_id:
                target_node = self.nodes.get(e["from"])
                neighbors.append({
                    "relationship": e["rel"],
                    "direction": "IN",
                    "target_id": e["from"],
                    "target_node": target_node,
                    "node": target_node.get("properties", {}) if target_node else {},
                    "properties": e["properties"]
                })
        return neighbors


class GraphDatabase:
    """
    Unified database interface for CodeGraph.
    Delegates to FalkorDB when connected, or LocalMemoryGraph when offline.
    """
    def __init__(self):
        self.is_falkordb = False
        self.falkor_client = None
        self.falkor_graph = None
        self.memory_graph = LocalMemoryGraph()
        self._init_connection()

    def _init_connection(self):
        try:
            from falkordb import FalkorDB
            client = FalkorDB(
                host=settings.falkordb_host,
                port=settings.falkordb_port,
                password=settings.falkordb_password if settings.falkordb_password else None
            )
            # Test connection
            graph = client.select_graph(settings.falkordb_graph)
            # Execute simple ping
            graph.query("RETURN 1 AS ping")
            self.falkor_client = client
            self.falkor_graph = graph
            self.is_falkordb = True
            logger.info(f"Connected to FalkorDB at {settings.falkordb_host}:{settings.falkordb_port}")
        except Exception as e:
            if settings.auto_fallback:
                self.is_falkordb = False
                logger.info(f"FalkorDB not reachable ({e}). Using local in-memory graph fallback.")
            else:
                raise ConnectionError(f"Failed to connect to FalkorDB: {e}")

    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "backend": "FalkorDB" if self.is_falkordb else "LocalMemoryGraph (Fallback)",
            "host": settings.falkordb_host if self.is_falkordb else "local-in-memory",
            "port": settings.falkordb_port if self.is_falkordb else 0,
            "graph_name": settings.falkordb_graph,
            "node_count": len(self.memory_graph.nodes) if not self.is_falkordb else "dynamic",
            "edge_count": len(self.memory_graph.edges) if not self.is_falkordb else "dynamic",
        }

    def execute_cypher(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executes Cypher on FalkorDB if connected, or logs it when in local fallback mode.
        """
        if self.is_falkordb and self.falkor_graph:
            return self.falkor_graph.query(cypher, params or {})
        return None

    def create_node(self, node_id: str, label: str, properties: Dict[str, Any]):
        # Always update memory store for consistent local cache
        self.memory_graph.add_node(node_id, label, properties)
        if self.is_falkordb and self.falkor_graph:
            # Escape strings safely for Cypher
            props_str = json.dumps(properties)
            cypher = f"MERGE (n:{label} {{id: $id}}) SET n += $props"
            self.falkor_graph.query(cypher, {"id": node_id, "props": properties})

    def create_edge(self, from_id: str, rel_type: str, to_id: str, properties: Optional[Dict[str, Any]] = None):
        self.memory_graph.add_edge(from_id, rel_type, to_id, properties)
        if self.is_falkordb and self.falkor_graph:
            cypher = f"""
            MATCH (a {{id: $from_id}}), (b {{id: $to_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $props
            """
            self.falkor_graph.query(cypher, {"from_id": from_id, "to_id": to_id, "props": properties or {}})

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        dir_val = "out" if direction == "outgoing" else ("in" if direction == "incoming" else direction)
        return self.memory_graph.get_neighbors(node_id, dir_val)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.memory_graph.nodes.get(node_id)

    def search_nodes(self, keyword: Optional[str] = None, label: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for nid, n in self.memory_graph.nodes.items():
            if label and n.get("label") != label:
                continue
            if not keyword:
                results.append(n)
                continue
            props = n.get("properties", {})
            for val in props.values():
                if keyword.lower() in str(val).lower():
                    results.append(n)
                    break
        return results

    def flush(self):
        """Persist memory graph changes to disk."""
        self.memory_graph.save()

    def clear(self):
        """Reset the graph."""
        self.memory_graph.clear()
        if self.is_falkordb and self.falkor_graph:
            try:
                self.falkor_graph.delete()
            except Exception:
                pass


# Global singleton instance
db = GraphDatabase()
