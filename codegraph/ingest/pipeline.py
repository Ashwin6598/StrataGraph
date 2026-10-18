"""
Unified Production Ingestion Pipeline and Auto-Linker for CodeGraph.
Orchestrates ingesting real-world Codebases, PRDs, ADRs, Runbooks, and Git histories,
then automatically synthesizes cross-entity relationships via AST annotations,
docstring metadata, and commit lineage.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..schema import ProjectNode, ChangeTimelineNode, Relationships
from ..db import db
from ..config import settings
from .code_parser import CodebaseParser
from .prd_parser import PRDParser
from .adr_parser import ADRParser
from .change_tracker import ChangeTracker
from .document_converter import SUPPORTED_DOC_EXTENSIONS


class IngestionPipeline:
    def __init__(
        self,
        project_name: str = "Enterprise Service",
        project_id: str = "project:enterprise",
        repo_url: str = "https://github.com/organization/repo",
        codebase_owner: Optional[str] = None,
        prd_owner: Optional[str] = None,
        architect_owner: Optional[str] = None
    ):
        self.project_name = project_name
        self.project_id = project_id
        self.repo_url = repo_url
        self.codebase_owner = codebase_owner or settings.codebase_owner
        self.prd_owner = prd_owner or settings.prd_owner
        self.architect_owner = architect_owner or settings.architect_owner
        self.code_parser = CodebaseParser()
        self.prd_parser = PRDParser()
        self.adr_parser = ADRParser()
        self.change_tracker = ChangeTracker()

    def run(
        self,
        code_dir: Optional[str] = None,
        prd_dir: Optional[str] = None,
        adr_dir: Optional[str] = None,
        runbook_dir: Optional[str] = None,
        git_repo_path: Optional[str] = None,
        jira_file: Optional[str] = None,
        max_commits: int = 50
    ) -> Dict[str, Any]:
        """
        Executes the full end-to-end ingestion pipeline and auto-links all cross-entity relationships.
        """
        summary = {
            "project_id": self.project_id,
            "codebase_owner": self.codebase_owner,
            "prd_owner": self.prd_owner,
            "architect_owner": self.architect_owner,
            "code_files_processed": 0,
            "prds_processed": 0,
            "adrs_processed": 0,
            "runbooks_processed": 0,
            "commits_ingested": 0,
            "jira_epics_processed": 0,
            "jira_features_processed": 0,
            "jira_stories_processed": 0,
            "cross_links_created": 0
        }

        # 1. Initialize Root Project Node
        project_node = ProjectNode(
            id=self.project_id,
            name=self.project_name,
            description=f"Automated knowledge graph for {self.project_name}",
            repository=self.repo_url,
            codebase_owner=self.codebase_owner,
            prd_owner=self.prd_owner,
            architect_owner=self.architect_owner
        )
        db.create_node(self.project_id, "Project", project_node.model_dump())

        # 2. Ingest Codebase
        if code_dir and Path(code_dir).exists():
            code_results = self.code_parser.parse_directory(code_dir)
            summary["code_files_processed"] = len(code_results)

        # 3. Ingest PRDs
        if prd_dir and Path(prd_dir).exists():
            for p in sorted(Path(prd_dir).iterdir()):
                if p.suffix.lower() in SUPPORTED_DOC_EXTENSIONS and not p.name.startswith("."):
                    res = self.prd_parser.parse_file(str(p))
                    if res.get("status") == "INGESTED":
                        summary["prds_processed"] += 1

        # 4. Ingest ADRs
        if adr_dir and Path(adr_dir).exists():
            for a in sorted(Path(adr_dir).iterdir()):
                if a.suffix.lower() in SUPPORTED_DOC_EXTENSIONS and not a.name.startswith("."):
                    res = self.adr_parser.parse_file(str(a))
                    if res.get("status") == "INGESTED":
                        summary["adrs_processed"] += 1

        # 5. Ingest Incident Runbooks
        if runbook_dir and Path(runbook_dir).exists():
            for r in sorted(Path(runbook_dir).iterdir()):
                if r.suffix.lower() in SUPPORTED_DOC_EXTENSIONS and not r.name.startswith("."):
                    res = self.change_tracker.parse_runbook(str(r))
                    if res.get("status") == "INGESTED":
                        summary["runbooks_processed"] += 1

        # 6. Extract Git Commits & Change Timeline
        if git_repo_path and Path(git_repo_path).exists():
            commits = self._extract_git_commits(git_repo_path, max_commits=max_commits)
            summary["commits_ingested"] = len(commits)

        # 7. Ingest Jira Board & Agile Execution (5th Pillar)
        if jira_file and Path(jira_file).exists():
            from .jira_parser import JiraBoardParser
            jparser = JiraBoardParser(project_id=self.project_id)
            jres = jparser.parse_file(jira_file)
            for epic in jres["epics"]:
                db.create_node(epic.id, "Epic", epic.model_dump())
            for feat in jres["features"]:
                db.create_node(feat.id, "AgileFeature", feat.model_dump())
            for story in jres["stories"]:
                db.create_node(story.id, "Story", story.model_dump())
            for from_id, rel, to_id in jres["edges"]:
                db.create_edge(from_id, rel, to_id)
            summary["jira_epics_processed"] = len(jres["epics"])
            summary["jira_features_processed"] = len(jres["features"])
            summary["jira_stories_processed"] = len(jres["stories"])

        # 8. Synthesize Cross-Entity Links (Auto-Linker)
        links_count = self._auto_link_cross_entities()
        summary["cross_links_created"] = links_count

        db.flush()
        return {
            "status": "SUCCESS",
            "summary": summary,
            "graph_stats": {
                "nodes": len(db.memory_graph.nodes),
                "edges": len(db.memory_graph.edges)
            }
        }

    def _extract_git_commits(self, repo_path: str, max_commits: int = 50) -> List[Dict[str, Any]]:
        """Extracts recent commit history via standard git log."""
        commits = []
        try:
            cmd = [
                "git", "-C", repo_path, "log",
                f"-n{max_commits}",
                "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
                "--date=short"
            ]
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
            for line in output.strip().split("\n"):
                if not line or "\x1f" not in line:
                    continue
                parts = line.split("\x1f")
                if len(parts) >= 4:
                    chash, author, date, message = parts[0], parts[1], parts[2], parts[3]
                    cid = f"timeline:commit:{chash[:7]}"

                    # Categorize commit
                    category = "REFACTOR"
                    msg_lower = message.lower()
                    if "feat" in msg_lower or "req-" in msg_lower or "prd" in msg_lower:
                        category = "PRD_FEATURE"
                    elif "adr" in msg_lower or "arch" in msg_lower:
                        category = "ADR_ENFORCEMENT"
                    elif "fix" in msg_lower or "bug" in msg_lower or "hotfix" in msg_lower:
                        category = "OPERATION_FIX"

                    timeline_node = ChangeTimelineNode(
                        id=cid,
                        project_id=self.project_id,
                        commit_hash=chash,
                        author=author,
                        timestamp=f"{date}T12:00:00Z",
                        date=date,
                        what_changed=message,
                        why_changed=f"Recorded from git commit message: {message}",
                        change_category=category,
                        diff_summary=message
                    )
                    db.create_node(cid, "ChangeTimeline", timeline_node.model_dump())
                    db.create_edge(self.project_id, "HAS_TIMELINE_RECORD", cid)
                    commits.append(timeline_node.model_dump())
        except Exception:
            # Fallback gracefully if git command is not in path or not a git repository
            pass
        return commits

    def _auto_link_cross_entities(self) -> int:
        """
        Scans all nodes, docstrings, commit logs, and markdown text to automatically create
        cross-entity relationships between CodeBase, PRDs, ADRs, Operations, and Timeline.
        """
        links_created = 0

        # Build lookup tables
        req_nodes = {}
        decision_nodes = {}
        issue_nodes = {}
        function_nodes = {}

        for nid, node in db.memory_graph.nodes.items():
            label = node["label"]
            props = node["properties"]
            if label in ("Requirement", "FunctionalRequirement"):
                req_id = props.get("id") or nid
                req_nodes[req_id] = nid
            elif label == "Decision":
                adr_id = props.get("adr_id")
                if adr_id:
                    decision_nodes[adr_id] = nid
                decision_nodes[nid] = nid
            elif label in ("Issue", "BugFix"):
                ticket = props.get("ticket") or nid
                issue_nodes[ticket] = nid
                issue_nodes[nid] = nid
            elif label == "Function":
                fname = props.get("name") or nid
                function_nodes[fname] = nid
                function_nodes[nid] = nid

        # 1. Scan Function Docstrings & Comments for REQ, ADR, and BUG tags
        for nid, node in list(db.memory_graph.nodes.items()):
            if node["label"] != "Function":
                continue
            doc = node["properties"].get("docstring") or ""
            if not doc:
                continue

            # Link Function -> PRD Requirement (e.g., 'Implements REQ-003')
            req_matches = re.findall(r"(REQ-[0-9A-Za-z_-]+)", doc)
            for rm in req_matches:
                target_req = req_nodes.get(rm) or req_nodes.get(f"req:{rm}")
                if target_req:
                    db.create_edge(target_req, Relationships.IMPLEMENTED_BY_FUNCTION, nid)
                    links_created += 1

            # Link ADR Decision -> Function (e.g., 'Governed by ADR-001')
            adr_matches = re.findall(r"(ADR-[0-9]+)", doc)
            for am in adr_matches:
                target_dec = decision_nodes.get(am) or decision_nodes.get(f"decision:{am}:core") or decision_nodes.get(f"dec:{am}:core")
                if target_dec:
                    db.create_edge(target_dec, Relationships.CONSTRAINS_FUNCTION, nid)
                    links_created += 1

            # Link Operations Issue -> Function (e.g., 'caused BUG-112')
            bug_matches = re.findall(r"(BUG-[0-9]+)", doc)
            for bm in bug_matches:
                target_iss = issue_nodes.get(bm) or issue_nodes.get(f"issue:{bm}")
                if target_iss:
                    db.create_edge(target_iss, Relationships.MANIFESTED_IN_FUNCTION, nid)
                    links_created += 1

        # 2. Scan ChangeTimeline commits for motivations
        for nid, node in list(db.memory_graph.nodes.items()):
            if node["label"] != "ChangeTimeline":
                continue
            what = node["properties"].get("what_changed", "")

            # Check for REQ matches
            req_matches = re.findall(r"(REQ-[0-9A-Za-z_-]+)", what)
            for rm in req_matches:
                target_req = req_nodes.get(rm) or req_nodes.get(f"req:{rm}")
                if target_req:
                    db.create_edge(nid, Relationships.MOTIVATED_BY_PRD, target_req)
                    links_created += 1

            # Check for ADR matches
            adr_matches = re.findall(r"(ADR-[0-9]+)", what)
            for am in adr_matches:
                target_dec = decision_nodes.get(am)
                if target_dec:
                    db.create_edge(nid, Relationships.MOTIVATED_BY_ADR, target_dec)
                    links_created += 1

            # Check for BUG matches
            bug_matches = re.findall(r"(BUG-[0-9]+)", what)
            for bm in bug_matches:
                target_iss = issue_nodes.get(bm) or issue_nodes.get(f"issue:{bm}")
                if target_iss:
                    db.create_edge(nid, Relationships.MOTIVATED_BY_FIX, target_iss)
                    links_created += 1

        return links_created
