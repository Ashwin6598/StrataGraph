"""
Multi-Language Code Parser for CodeGraph.
Supports Python (via standard library AST) and TypeScript, JavaScript, Go,
Java, Kotlin, Rust, C#, and C/C++ via zero-dependency universal lexer.
Extracts File, Class, Function, and Call-Hierarchy nodes.
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from ..schema import FileNode, ClassNode, FunctionNode, Relationships
from ..db import db

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rs": "rust",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c"
}


class CodebaseParser:
    def __init__(self):
        self.functions: Dict[str, FunctionNode] = {}
        self.classes: Dict[str, ClassNode] = {}
        self.calls: List[Tuple[str, str]] = []  # (caller_fn, callee_fn)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        path_obj = Path(file_path)
        if not path_obj.exists() or path_obj.suffix not in SUPPORTED_EXTENSIONS:
            return {"status": "SKIPPED", "path": file_path}

        language = SUPPORTED_EXTENSIONS[path_obj.suffix]

        if language == "python":
            return self._parse_python(file_path, path_obj)
        else:
            return self._parse_universal(file_path, path_obj, language)

    def _parse_python(self, file_path: str, path_obj: Path) -> Dict[str, Any]:
        """Parses Python files using standard library AST for 100% precision."""
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

                fn_source = ast.get_source_segment(source, node)

                func_node = FunctionNode(
                    id=func_id,
                    name=node.name,
                    file_path=file_path,
                    signature=sig,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=doc,
                    class_name=v_self.current_class,
                    class_id=f"class:{path_obj.name}:{v_self.current_class}" if v_self.current_class else None,
                    source_code=fn_source
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
                            target_id = f"func_call_target:{called_name}"
                            db.create_edge(func_id, Relationships.CALLS, target_id, {"callee_name": called_name})

                v_self.generic_visit(node)

        visitor = Visitor()
        visitor.visit(tree)
        return {"status": "INGESTED", "path": file_path, "file_id": file_id, "language": "python"}

    def _parse_universal(self, file_path: str, path_obj: Path, language: str) -> Dict[str, Any]:
        """
        Universal lexer that parses TypeScript, JavaScript, Go, Java, Kotlin, Rust, C#, C/C++
        without external native dependencies.
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return {"status": "ERROR", "path": file_path, "error": str(e)}

        file_id = f"file:{path_obj.name}"
        db.create_node(
            node_id=file_id,
            label="File",
            properties={"path": file_path, "filename": path_obj.name, "language": language}
        )

        lines = content.split("\n")
        total_lines = len(lines)

        # 1. Extract Classes / Structs
        class_regexes = [
            r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_]+)",                   # TS/JS/Java/C#
            r"^\s*type\s+([A-Za-z0-9_]+)\s+struct",                        # Go
            r"^\s*(?:pub\s+)?struct\s+([A-Za-z0-9_]+)",                    # Rust
        ]

        active_class = None
        for i, line in enumerate(lines, 1):
            for cr in class_regexes:
                cm = re.search(cr, line)
                if cm:
                    cname = cm.group(1)
                    class_id = f"class:{path_obj.name}:{cname}"
                    cnode = ClassNode(
                        id=class_id,
                        name=cname,
                        file_path=file_path,
                        line_start=i,
                        line_end=min(i + 50, total_lines),
                        docstring=f"{language.capitalize()} class/struct {cname}"
                    )
                    db.create_node(class_id, "Class", cnode.model_dump())
                    db.create_edge(file_id, Relationships.CONTAINS_CLASS, class_id)
                    active_class = cname
                    break

        # 2. Extract Functions / Methods
        # Patterns for TS/JS, Go, Java/Kotlin, Rust
        func_patterns = [
            # TypeScript/JavaScript function or exported arrow
            (r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)", 1, 2),
            (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=]+)?\s*=>", 1, 2),
            # TypeScript/JavaScript class method: async methodName(args): ReturnType {
            (r"^\s*(?:(?:public|private|protected|static|async|override)\s+)+([A-Za-z0-9_]+)\s*\(([^)]*)\)", 1, 2),
            # Go function / method
            (r"func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(([^)]*)\)", 1, 2),
            # Rust fn
            (r"(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)", 1, 2),
            # Kotlin fun
            (r"fun\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)", 1, 2),
            # Java / C# method: public void methodName(arg1, arg2) {
            (r"(?:public|private|protected|static|final|\s)*\s+[\w<>\[\],\s]+\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{", 1, 2),
        ]

        fn_count = 0
        for i, line in enumerate(lines, 1):
            clean_line = line.strip()
            # Skip comments or control-flow keywords masquerading as functions
            if clean_line.startswith(("//", "/*", "*", "#")) or re.match(r"^(if|while|for|switch|catch)\s*\(", clean_line):
                continue

            for pattern, name_idx, arg_idx in func_patterns:
                match = re.search(pattern, line)
                if match:
                    fname = match.group(name_idx)
                    # Ignore common reserved keywords
                    if fname in ("if", "for", "while", "switch", "catch", "return", "class", "function", "constructor"):
                        continue

                    raw_args = match.group(arg_idx) if arg_idx else ""
                    args = [a.strip() for a in raw_args.split(",") if a.strip()]
                    sig = f"{fname}({', '.join(args)})"

                    # Calculate end line via brace counting or heuristic
                    end_line = i
                    brace_count = line.count("{") - line.count("}")
                    if "{" in line:
                        for j in range(i, min(i + 150, total_lines)):
                            brace_count += lines[j].count("{") - lines[j].count("}")
                            if brace_count <= 0 and j > i:
                                end_line = j + 1
                                break
                    if end_line == i:
                        end_line = min(i + 20, total_lines)

                    # Extract preceding comment/docstring
                    doc_lines = []
                    k = i - 2
                    while k >= 0 and k >= i - 10:
                        prev = lines[k].strip()
                        if prev.startswith(("//", "/*", "*", "#", "///", "/**")):
                            doc_lines.insert(0, prev.lstrip("/*# /").rstrip("*/"))
                            k -= 1
                        else:
                            break
                    doc = "\n".join(doc_lines) if doc_lines else None

                    # Extract source code block
                    fn_source = "\n".join(lines[i - 1:end_line])

                    func_id = f"func:{path_obj.name}:{fname}"
                    func_node = FunctionNode(
                        id=func_id,
                        name=fname,
                        file_path=file_path,
                        signature=sig,
                        line_start=i,
                        line_end=end_line,
                        docstring=doc,
                        class_name=active_class,
                        class_id=f"class:{path_obj.name}:{active_class}" if active_class else None,
                        source_code=fn_source
                    )
                    db.create_node(func_id, "Function", func_node.model_dump())
                    db.create_edge(file_id, Relationships.CONTAINS_FUNC, func_id)

                    if active_class:
                        class_id = f"class:{path_obj.name}:{active_class}"
                        db.create_edge(class_id, Relationships.CLASS_METHOD, func_id)

                    # Find outgoing calls in function body
                    for call_match in re.finditer(r"([A-Za-z0-9_]{3,})\s*\(", fn_source):
                        callee = call_match.group(1)
                        if callee != fname and callee not in ("if", "for", "while", "switch", "catch", "return", "require", "import", "println", "fmt", "console"):
                            target_id = f"func_call_target:{callee}"
                            db.create_edge(func_id, Relationships.CALLS, target_id, {"callee_name": callee})

                    fn_count += 1
                    break

        return {"status": "INGESTED", "path": file_path, "file_id": file_id, "functions_count": fn_count, "language": language}

    def parse_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        results = []
        for root, _, files in os.walk(dir_path):
            for file in sorted(files):
                ext = Path(file).suffix
                if ext in SUPPORTED_EXTENSIONS and not file.startswith("__"):
                    full_path = os.path.join(root, file)
                    results.append(self.parse_file(full_path))

        # Reconcile function calls
        for edge in list(db.memory_graph.edges):
            if edge["rel"] == Relationships.CALLS and edge["to"].startswith("func_call_target:"):
                callee = edge["properties"].get("callee_name")
                for node_id, node_data in db.memory_graph.nodes.items():
                    if node_data["label"] == "Function" and node_data["properties"].get("name") == callee:
                        db.create_edge(edge["from"], Relationships.CALLS, node_id, {"callee_name": callee})
                        break

        db.flush()
        return results
