"""
Code parser for CodeGraph.
Uses standard library `ast` to parse Python files into File, Class, and Function nodes and call hierarchies.
Zero external dependencies.
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from ..schema import FileNode, ClassNode, FunctionNode, Relationships
from ..db import db


class CodebaseParser:
    def __init__(self):
        self.functions: Dict[str, FunctionNode] = {}
        self.classes: Dict[str, ClassNode] = {}
        self.calls: List[Tuple[str, str]] = []  # (caller_fn, callee_fn)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        path_obj = Path(file_path)
        if not path_obj.exists() or not path_obj.suffix == ".py":
            return {"status": "SKIPPED", "path": file_path}

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            return {"status": "ERROR", "path": file_path, "error": str(e)}

        file_id = f"file:{path_obj.name}"
        db.create_node(
            node_id=file_id,
            label="File",
            properties={"path": file_path, "filename": path_obj.name, "language": "python"}
        )

        current_class = None

        class Visitor(ast.NodeVisitor):
            def __init__(v_self):
                v_self.current_class = None

            def visit_ClassDef(v_self, node: ast.ClassDef):
                class_id = f"class:{path_obj.name}:{node.name}"
                doc = ast.get_docstring(node)
                class_node = ClassNode(
                    id=class_id,
                    name=node.name,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=doc
                )
                db.create_node(
                    node_id=class_id,
                    label="Class",
                    properties=class_node.model_dump()
                )
                db.create_edge(file_id, Relationships.CONTAINS_CLASS, class_id)

                prev_class = v_self.current_class
                v_self.current_class = node.name
                v_self.generic_visit(node)
                v_self.current_class = prev_class

            def visit_FunctionDef(v_self, node: ast.FunctionDef):
                func_id = f"func:{path_obj.name}:{node.name}"
                doc = ast.get_docstring(node)

                # Build argument signature
                args = [arg.arg for arg in node.args.args]
                sig = f"{node.name}({', '.join(args)})"

                func_node = FunctionNode(
                    id=func_id,
                    name=node.name,
                    file_path=file_path,
                    signature=sig,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=doc,
                    class_name=v_self.current_class,
                    class_id=f"class:{path_obj.name}:{v_self.current_class}" if v_self.current_class else None
                )
                db.create_node(
                    node_id=func_id,
                    label="Function",
                    properties=func_node.model_dump()
                )
                db.create_edge(file_id, Relationships.CONTAINS_FUNC, func_id)

                if v_self.current_class:
                    class_id = f"class:{path_obj.name}:{v_self.current_class}"
                    db.create_edge(class_id, Relationships.CLASS_METHOD, func_id)

                # Inspect inner calls
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Call):
                        called_name = None
                        if isinstance(inner_node.func, ast.Name):
                            called_name = inner_node.func.id
                        elif isinstance(inner_node.func, ast.Attribute):
                            called_name = inner_node.func.attr

                        if called_name and called_name != node.name:
                            # Candidate function call
                            target_id = f"func_call_target:{called_name}"
                            db.create_edge(func_id, Relationships.CALLS, target_id, {"callee_name": called_name})

                v_self.generic_visit(node)

        visitor = Visitor()
        visitor.visit(tree)
        return {"status": "INGESTED", "path": file_path, "file_id": file_id}

    def parse_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        results = []
        for root, _, files in os.walk(dir_path):
            for file in sorted(files):
                if file.endswith(".py") and not file.startswith("__"):
                    full_path = os.path.join(root, file)
                    results.append(self.parse_file(full_path))

        # Reconcile function calls
        # Connect func_call_target edges to actual functions if names match
        for edge in list(db.memory_graph.edges):
            if edge["rel"] == Relationships.CALLS and edge["to"].startswith("func_call_target:"):
                callee = edge["properties"].get("callee_name")
                for node_id, node_data in db.memory_graph.nodes.items():
                    if node_data["label"] == "Function" and node_data["properties"].get("name") == callee:
                        # Add resolved call edge
                        db.create_edge(edge["from"], Relationships.CALLS, node_id, {"callee_name": callee})
                        break

        db.flush()
        return results
