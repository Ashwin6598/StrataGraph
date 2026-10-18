"""
Shared MCP Tools for CodeGraph.
Provides global graph search, multi-hop neighborhood exploration, and traversal explainability.
"""

from typing import Dict, Any, List, Optional
from ..db import db
from ..schema import ExplainableResult, TraversalStep


def search_graph(query: str, entity_type: Optional[str] = None, limit: int = 15) -> Dict[str, Any]:
    """
    Performs full-text search across all nodes in the knowledge graph.
    Matches across PRDs, Requirements, Scenarios, ADRs, Code Functions, BugFixes, and Runbooks.
    """
    if entity_type:
        cypher = f"""
        MATCH (n:{entity_type})
        WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $query)
        RETURN n LIMIT $limit
        """
    else:
        # Rule 5: Explicit labels over core GraphBLAS matrices
        cypher = """
        MATCH (n)
        WHERE any(lbl IN labels(n) WHERE lbl IN ['Project', 'Function', 'FunctionalRequirement', 'Decision', 'Issue', 'Epic', 'AgileFeature', 'Story'])
          AND any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $query)
        RETURN n LIMIT $limit
        """

    db.execute_cypher(cypher, {"query": query, "limit": limit})

    query_lower = query.lower()
    matches = []

    for nid, node in db.memory_graph.nodes.items():
        if entity_type and node["label"].lower() != entity_type.lower():
            continue

        props = node["properties"]
        # Match any string property
        matched_field = None
        for k, v in props.items():
            if query_lower in str(v).lower():
                matched_field = k
                break

        if matched_field:
            matches.append({
                "node_id": nid,
                "label": node["label"],
                "matched_field": matched_field,
                "properties": props
            })
            if len(matches) >= limit:
                break

    return ExplainableResult(
        result={
            "query": query,
            "total_matches": len(matches),
            "matches": matches
        },
        cypher_query=cypher.strip(),
        traversal_path=[],
        explanation=f"Full-text property scan across {len(db.memory_graph.nodes)} graph nodes."
    ).model_dump()


def get_related_entities(node_id: str, hops: int = 2) -> Dict[str, Any]:
    """
    Performs an N-hop graph neighborhood expansion starting from any node ID.
    Finds all directly and transitively connected business, technical, and quality artifacts.
    """
    start_node = db.get_node(node_id)
    start_label = start_node.get("label") if start_node else db.resolve_label(node_id)
    label_clause = f":{start_label}" if start_label else ""
    bounded_hops = min(max(1, hops), 5)

    cypher = f"""
    MATCH path = (start{label_clause} {{id: $node_id}})-[*1..{bounded_hops}]-(connected)
    RETURN path
    """
    db.execute_cypher(cypher, {"node_id": node_id})

    if node_id not in db.memory_graph.nodes:
        # Try finding by name or ticket
        matched_id = None
        for nid, n in db.memory_graph.nodes.items():
            if n["properties"].get("name") == node_id or n["properties"].get("id") == node_id or n["properties"].get("ticket") == node_id:
                matched_id = nid
                break
        if matched_id:
            node_id = matched_id
        else:
            return ExplainableResult(
                result={"error": f"Node '{node_id}' not found in graph"},
                cypher_query=cypher.strip(),
                traversal_path=[],
                explanation="Node not found"
            ).model_dump()

    visited = {node_id}
    queue = [(node_id, 0)]
    related_nodes = []
    edges_traversed = []
    traversal_path = []

    while queue:
        curr_id, curr_depth = queue.pop(0)
        if curr_depth >= hops:
            continue

        neighbors = db.memory_graph.get_neighbors(curr_id, direction="both")
        for nb in neighbors:
            target_id = nb["target_id"]
            if target_id and target_id not in visited:
                visited.add(target_id)
                target_node = nb["target_node"] or {}
                related_nodes.append({
                    "node_id": target_id,
                    "label": target_node.get("label", "Unknown"),
                    "depth_hops": curr_depth + 1,
                    "connected_via": nb["relationship"],
                    "direction": nb["direction"],
                    "title_or_name": target_node.get("properties", {}).get("title") or target_node.get("properties", {}).get("name") or target_id
                })
                traversal_path.append(TraversalStep(
                    from_node=curr_id,
                    relationship=nb["relationship"],
                    to_node=target_id,
                    explanation=f"Hop {curr_depth + 1}: {curr_id} -[{nb['relationship']}]-> {target_id}"
                ))
                queue.append((target_id, curr_depth + 1))

    return ExplainableResult(
        result={
            "root_node_id": node_id,
            "root_label": db.memory_graph.nodes[node_id].get("label"),
            "hops": hops,
            "connected_entities_count": len(related_nodes),
            "connected_entities": related_nodes
        },
        cypher_query=cypher.strip(),
        traversal_path=traversal_path,
        explanation=f"Multi-hop breadth-first traversal up to {hops} degrees of separation."
    ).model_dump()


def explain_traversal(steps: List[Dict[str, Any]]) -> str:
    """
    Renders an ASCII visualization of graph traversal steps to verify explainable execution paths and lineage.
    """
    lines = ["📊 Graph Traversal Path Visualization:"]
    for i, s in enumerate(steps, 1):
        lines.append(f"  {i}. ({s.get('from_node')}) --[{s.get('relationship')}]--> ({s.get('to_node')})")
        if s.get("explanation"):
            lines.append(f"     💡 Context: {s.get('explanation')}")
    return "\n".join(lines)
