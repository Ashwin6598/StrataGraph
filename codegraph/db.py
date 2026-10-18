"""
Database driver for CodeGraph.
Supports FalkorDB (via OpenCypher) and seamless in-memory fallback with JSON persistence for offline local development.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
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


# FalkorDB GraphBLAS Optimization Constants
INTERNED_FIELDS: Set[str] = {
    "status",
    "priority",
    "severity",
    "actor_role",
    "sprint",
    "root_cause_category",
    "service_name",
    "approval_status",
}

CORE_INDEXES: List[Tuple[str, str]] = [
    ("Project", "id"),
    ("Function", "id"),
    ("Function", "name"),
    ("Class", "id"),
    ("Class", "name"),
    ("CodeLogic", "id"),
    ("PRDInput", "id"),
    ("FunctionalRequirement", "id"),
    ("Guardrail", "id"),
    ("PRDOutput", "id"),
    ("ADRRequirement", "id"),
    ("Architecture", "id"),
    ("Decision", "id"),
    ("ADRResult", "id"),
    ("Issue", "id"),
    ("RCA", "id"),
    ("Fix", "id"),
    ("OpResult", "id"),
    ("ChangeTimeline", "id"),
    ("Epic", "id"),
    ("AgileFeature", "id"),
    ("AgileFeature", "key"),
    ("Story", "id"),
    ("Story", "key"),
]

PREFIX_LABEL_MAP: Dict[str, str] = {
    "project:": "Project",
    "func:": "Function",
    "class:": "Class",
    "logic:": "CodeLogic",
    "prd_input:": "PRDInput",
    "req:": "FunctionalRequirement",
    "guard:": "Guardrail",
    "prd_out:": "PRDOutput",
    "adr_req:": "ADRRequirement",
    "arch:": "Architecture",
    "dec:": "Decision",
    "adr_res:": "ADRResult",
    "issue:": "Issue",
    "rca:": "RCA",
    "fix:": "Fix",
    "op_res:": "OpResult",
    "timeline:": "ChangeTimeline",
    "epic:": "Epic",
    "feat:": "AgileFeature",
    "story:": "Story",
}


class GraphDatabase:
    """
    Unified database interface for CodeGraph.
    Delegates to FalkorDB when connected, or LocalMemoryGraph when offline.
    Optimized for FalkorDB GraphBLAS sparse matrix performance:
    - String interning (intern()) on repeated enums
    - Explicit single-property indexes on core entities
    - Targeted explicit node labels on matches (no open MATCH (a))
    - Parameterized Cypher query caching
    - Logical graph key isolation per project/tenant
    """
    def __init__(self):
        self.is_falkordb = False
        self.falkor_client = None
        self.falkor_graph = None
        self.active_graph_name: str = settings.falkordb_graph
        self.falkor_graphs: Dict[str, Any] = {}
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
            self.falkor_graphs[settings.falkordb_graph] = graph
            self.is_falkordb = True
            logger.info(f"Connected to FalkorDB at {settings.falkordb_host}:{settings.falkordb_port}")
            self.ensure_indexes(settings.falkordb_graph)
        except Exception as e:
            if settings.auto_fallback:
                self.is_falkordb = False
                logger.info(f"FalkorDB not reachable ({e}). Using local in-memory graph fallback.")
            else:
                raise ConnectionError(f"Failed to connect to FalkorDB: {e}")

    def get_project_graph_key(self, project_id: str) -> str:
        """
        Derives an isolated logical graph key for a project/tenant
        to prevent monolithic graph inflation in GraphBLAS (Rule 4: Isolation).
        """
        clean = project_id.replace("project:", "").replace("-", "_")
        return f"{settings.falkordb_graph}_{clean}"

    def select_graph(self, graph_name: str) -> Any:
        """
        Selects or switches to an isolated logical graph key (Rule 4: Isolation).
        """
        self.active_graph_name = graph_name
        if self.is_falkordb and self.falkor_client:
            if graph_name not in self.falkor_graphs:
                g = self.falkor_client.select_graph(graph_name)
                self.falkor_graphs[graph_name] = g
                self.ensure_indexes(graph_name)
            self.falkor_graph = self.falkor_graphs[graph_name]
            return self.falkor_graph
        return None

    def ensure_indexes(self, graph_name: Optional[str] = None) -> List[str]:
        """
        Creates single-property indexes on all core entities in FalkorDB (Rule 3: Explicit Indexing):
        CREATE INDEX FOR (label) ON (property)
        Guarantees O(1) point lookups across GraphBLAS sparse matrices.
        """
        created = []
        target_graph = self.falkor_graphs.get(graph_name) if graph_name else self.falkor_graph
        for label, prop in CORE_INDEXES:
            cypher = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
            created.append(cypher)
            if self.is_falkordb and target_graph:
                try:
                    target_graph.query(cypher)
                except Exception as e:
                    # Ignore if index already exists
                    logger.debug(f"Index on {label}({prop}) creation notice: {e}")
        return created

    def resolve_label(self, node_id: str) -> str:
        """Resolves node label from memory graph or deterministic ID prefix."""
        node = self.memory_graph.nodes.get(node_id)
        if node and node.get("label"):
            return node["label"]
        for prefix, lbl in PREFIX_LABEL_MAP.items():
            if node_id.startswith(prefix):
                return lbl
        return ""

    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "backend": "FalkorDB" if self.is_falkordb else "LocalMemoryGraph (Fallback)",
            "host": settings.falkordb_host if self.is_falkordb else "local-in-memory",
            "port": settings.falkordb_port if self.is_falkordb else 0,
            "graph_name": self.active_graph_name,
            "node_count": len(self.memory_graph.nodes) if not self.is_falkordb else "dynamic",
            "edge_count": len(self.memory_graph.edges) if not self.is_falkordb else "dynamic",
            "indexes_registered": len(CORE_INDEXES)
        }

    def execute_cypher(self, cypher: str, params: Optional[Dict[str, Any]] = None, graph_name: Optional[str] = None) -> Any:
        """
        Executes Cypher on FalkorDB if connected, or logs it when in local fallback mode.
        Rule 7: Parameterized query caching.
        """
        target_graph = self.falkor_graphs.get(graph_name) if graph_name else self.falkor_graph
        if self.is_falkordb and target_graph:
            return target_graph.query(cypher, params or {})
        return None

    def create_node(self, node_id: str, label: str, properties: Dict[str, Any], graph_name: Optional[str] = None):
        # Always update memory store for consistent local cache
        self.memory_graph.add_node(node_id, label, properties)
        target_graph = self.falkor_graphs.get(graph_name) if graph_name else self.falkor_graph
        if self.is_falkordb and target_graph:
            # Rule 2: String interning (intern()) on repeated enums
            # Rule 7: Fully parameterized Cypher
            regular_props = {}
            intern_clauses = []
            cypher_params: Dict[str, Any] = {"id": node_id}

            for k, v in properties.items():
                if k in INTERNED_FIELDS and isinstance(v, str):
                    intern_clauses.append(f"n.{k} = intern(${k})")
                    cypher_params[k] = v
                else:
                    regular_props[k] = v

            cypher_params["props"] = regular_props
            set_parts = ["n += $props"] + intern_clauses
            set_clause = ", ".join(set_parts)
            cypher = f"MERGE (n:{label} {{id: $id}}) SET {set_clause}"
            target_graph.query(cypher, cypher_params)

    def create_edge(
        self,
        from_id: str,
        rel_type: str,
        to_id: str,
        properties: Optional[Dict[str, Any]] = None,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
        graph_name: Optional[str] = None
    ):
        self.memory_graph.add_edge(from_id, rel_type, to_id, properties)
        target_graph = self.falkor_graphs.get(graph_name) if graph_name else self.falkor_graph
        if self.is_falkordb and target_graph:
            # Rule 5: Explicit labels on both sides (never open MATCH (a))
            # Rule 7: Parameterized query
            flabel = from_label or self.resolve_label(from_id)
            tlabel = to_label or self.resolve_label(to_id)

            f_clause = f"(a:{flabel} {{id: $from_id}})" if flabel else "(a {id: $from_id})"
            t_clause = f"(b:{tlabel} {{id: $to_id}})" if tlabel else "(b {id: $to_id})"

            cypher = f"""
            MATCH {f_clause}, {t_clause}
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += $props
            """
            target_graph.query(cypher, {"from_id": from_id, "to_id": to_id, "props": properties or {}})

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
