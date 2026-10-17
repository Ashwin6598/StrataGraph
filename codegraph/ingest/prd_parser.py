"""
PRD Parser for CodeGraph.
Extracts PRDs, Requirements, and Test/Functional Scenarios from structured markdown.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from ..schema import PRDNode, RequirementNode, ScenarioNode, Relationships
from ..db import db


class PRDParser:
    def parse_file(self, prd_path: str) -> Dict[str, Any]:
        path_obj = Path(prd_path)
        if not path_obj.exists():
            return {"status": "ERROR", "message": f"File {prd_path} does not exist"}

        with open(prd_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract Header Metadata
        doc_id_match = re.search(r"\*\*Document ID:\*\*\s*([^\n]+)", content)
        title_match = re.search(r"#\s*PRD:\s*([^\n]+)", content) or re.search(r"\*\*Title:\*\*\s*([^\n]+)", content)
        version_match = re.search(r"\*\*Version:\*\*\s*([^\n]+)", content)
        status_match = re.search(r"\*\*Status:\*\*\s*([^\n]+)", content)
        author_match = re.search(r"\*\*Author:\*\*\s*([^\n]+)", content)

        prd_id = doc_id_match.group(1).strip() if doc_id_match else f"prd:{path_obj.stem}"
        title = title_match.group(1).strip() if title_match else path_obj.stem
        version = version_match.group(1).strip() if version_match else "1.0"
        status = status_match.group(1).strip() if status_match else "APPROVED"
        author = author_match.group(1).strip() if author_match else None

        prd_node = PRDNode(
            id=prd_id,
            title=title,
            version=version,
            status=status,
            author=author
        )
        db.create_node(prd_id, "PRD", prd_node.model_dump())

        # Extract Requirements: ### REQ-xxx: Title
        req_blocks = re.split(r"(?=###\s+REQ-)", content)
        req_count = 0
        scenario_count = 0

        for block in req_blocks:
            header_match = re.match(r"###\s+(REQ-[0-9A-Za-z_-]+):\s*([^\n]+)", block)
            if not header_match:
                continue

            req_id = header_match.group(1).strip()
            req_title = header_match.group(2).strip()

            priority_match = re.search(r"\*\*Priority:\*\*\s*([^\n]+)", block)
            status_match = re.search(r"\*\*Status:\*\*\s*([^\n]+)", block)
            desc_match = re.search(r"\*\*Description:\*\*\s*([^\n]+)", block)

            priority = priority_match.group(1).strip() if priority_match else "MEDIUM"
            req_status = status_match.group(1).strip() if status_match else "IMPLEMENTED"
            desc = desc_match.group(1).strip() if desc_match else req_title

            req_node = RequirementNode(
                id=req_id,
                prd_id=prd_id,
                title=req_title,
                description=desc,
                priority=priority,
                status=req_status
            )
            db.create_node(req_id, "Requirement", req_node.model_dump())
            db.create_edge(prd_id, Relationships.CONTAINS_REQ, req_id)
            req_count += 1

            # Extract Scenarios within this requirement: - **SCEN-xxx:** description
            scenario_matches = re.finditer(r"-\s+\*\*(SCEN-[0-9A-Za-z_-]+):\*\*\s*([^\n]+)", block)
            for sm in scenario_matches:
                scen_id = sm.group(1).strip()
                scen_text = sm.group(2).strip()

                scen_node = ScenarioNode(
                    id=scen_id,
                    req_id=req_id,
                    description=scen_text,
                    expected_behavior=scen_text,
                    covered_by_code=(req_status == "IMPLEMENTED")
                )
                db.create_node(scen_id, "Scenario", scen_node.model_dump())
                db.create_edge(req_id, Relationships.HAS_SCENARIO, scen_id)
                scenario_count += 1

        db.flush()
        return {
            "status": "INGESTED",
            "prd_id": prd_id,
            "title": title,
            "requirements_ingested": req_count,
            "scenarios_ingested": scenario_count
        }
