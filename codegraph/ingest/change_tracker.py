"""
Change Tracker and Quality Ingestion for CodeGraph.
Parses Runbooks, Bug Fixes, Root Cause Analyses (RCA), and Git ChangeRecords.
Links quality lineage and architectural decisions to code functions.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from ..schema import BugFixNode, RunbookNode, ChangeRecordNode, Relationships
from ..db import db


from .document_converter import DocumentConverter


class ChangeTracker:
    def parse_runbook(self, runbook_path: str) -> Dict[str, Any]:
        path_obj = Path(runbook_path)
        if not path_obj.exists():
            return {"status": "ERROR", "message": f"Runbook {runbook_path} does not exist"}

        content = DocumentConverter.to_markdown(runbook_path)
        if not content:
            return {"status": "ERROR", "message": f"Could not extract markdown content from {runbook_path}"}

        rb_id_match = re.search(r"\*\*Runbook ID:\*\*\s*([^\n]+)", content)
        service_match = re.search(r"\*\*Service:\*\*\s*([^\n]+)", content)
        title_match = re.search(r"#\s*Runbook\s+([^:]+:\s*[^\n]+)", content)

        rb_id = rb_id_match.group(1).strip() if rb_id_match else f"rb:{path_obj.stem}"
        service = service_match.group(1).strip() if service_match else "payment-gateway"
        title = title_match.group(1).strip() if title_match else path_obj.stem

        # Extract Incident sections: ## 1. Incident: ...
        incidents = re.split(r"(?=##\s+[0-9]+\.\s+Incident:)", content)
        ingested_bugs = 0

        for inc in incidents:
            inc_title_match = re.match(r"##\s+[0-9]+\.\s+Incident:\s*([^\n]+)", inc)
            if not inc_title_match:
                continue

            symptom_name = inc_title_match.group(1).strip()
            symptom_match = re.search(r"\*\*Error Code / Symptom:\*\*\s*([^\n]+)", inc)
            symptom = symptom_match.group(1).strip() if symptom_match else symptom_name

            rca_match = re.search(r"\*\*Root Cause Analysis \(RCA\):\*\*\s*\n(.*?)(?=\n-|\Z)", inc, re.DOTALL)
            rca = rca_match.group(1).strip() if rca_match else "Unknown root cause"

            res_match = re.search(r"\*\*Verified Resolution:\*\*\s*\n(.*?)(?=\n##|\Z)", inc, re.DOTALL)
            res = res_match.group(1).strip() if res_match else "Follow standard recovery"

            # Check for BUG-xxx references
            bug_matches = re.findall(r"(BUG-[0-9]+)", inc)
            for bug_id in bug_matches:
                bug_node = BugFixNode(
                    id=bug_id,
                    ticket=bug_id,
                    symptom=symptom,
                    description=f"Incident {symptom_name}: {symptom}",
                    rca=rca,
                    fix_summary=res,
                    approved=True,
                    date="2026-02-15"
                )
                db.create_node(bug_id, "BugFix", bug_node.model_dump())
                ingested_bugs += 1

                # Create Runbook Node for this specific operational procedure
                proc_id = f"proc:{rb_id}:{bug_id}"
                rb_node = RunbookNode(
                    id=proc_id,
                    title=f"Procedure for {symptom_name}",
                    service=service,
                    symptom=symptom,
                    rca=rca,
                    resolution_steps=res,
                    raw_content=content
                )
                db.create_node(proc_id, "Runbook", rb_node.model_dump())
                db.create_edge(proc_id, Relationships.RESOLVES_BUG, bug_id)

        db.flush()
        return {
            "status": "INGESTED",
            "runbook_id": rb_id,
            "bugs_extracted": ingested_bugs
        }

    def record_commit(
        self,
        commit_hash: str,
        author: str,
        date: str,
        message: str,
        reason: str,
        reason_id: str,
        file_path: str,
        target_func_name: str
    ) -> Dict[str, Any]:
        """
        Records a commit into the knowledge graph and links to the target Function.
        """
        commit_id = f"commit:{commit_hash[:7]}"
        change_node = ChangeRecordNode(
            commit_hash=commit_hash,
            author=author,
            date=date,
            message=message,
            reason=reason,
            reason_id=reason_id,
            file_path=file_path
        )
        db.create_node(commit_id, "ChangeRecord", change_node.model_dump())

        # Link to target function
        for node_id, data in db.memory_graph.nodes.items():
            if data["label"] == "Function" and data["properties"].get("name") == target_func_name:
                db.create_edge(node_id, Relationships.CHANGED_BY, commit_id, {"reason": reason})

        db.flush()
        return {"status": "RECORDED", "commit_id": commit_id}
