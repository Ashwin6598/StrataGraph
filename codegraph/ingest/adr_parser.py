"""
ADR Parser for CodeGraph.
Extracts Architecture Decision Records and explicit technical constraints from markdown.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from ..schema import ADRNode, DecisionNode, Relationships
from ..db import db


class ADRParser:
    def parse_file(self, adr_path: str) -> Dict[str, Any]:
        path_obj = Path(adr_path)
        if not path_obj.exists():
            return {"status": "ERROR", "message": f"File {adr_path} does not exist"}

        with open(adr_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Metadata
        adr_id_match = re.search(r"\*\*ADR ID:\*\*\s*([^\n]+)", content)
        title_match = re.search(r"#\s*(ADR-[0-9]+:\s*[^\n]+)", content) or re.search(r"\*\*Title:\*\*\s*([^\n]+)", content)
        date_match = re.search(r"\*\*Date:\*\*\s*([^\n]+)", content)
        status_match = re.search(r"\*\*Status:\*\*\s*([^\n]+)", content)

        adr_id = adr_id_match.group(1).strip() if adr_id_match else f"adr:{path_obj.stem}"
        title = title_match.group(1).strip() if title_match else path_obj.stem
        date = date_match.group(1).strip() if date_match else "2026-01-01"
        status = status_match.group(1).strip() if status_match else "ACCEPTED"

        # Sections: Context, Decision, Consequences
        context_sec = re.search(r"## Context\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        decision_sec = re.search(r"## Decision\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        consequences_sec = re.search(r"## Consequences\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)

        context = context_sec.group(1).strip() if context_sec else ""
        decision = decision_sec.group(1).strip() if decision_sec else ""
        consequences = consequences_sec.group(1).strip() if consequences_sec else ""

        adr_node = ADRNode(
            id=adr_id,
            title=title,
            status=status,
            date=date,
            context=context,
            decision=decision,
            consequences=consequences
        )
        db.create_node(adr_id, "ADR", adr_node.model_dump())

        # Extract specific decisions
        dec_id = f"dec:{adr_id}:core"
        dec_node = DecisionNode(
            id=dec_id,
            arch_id=f"arch:{adr_id}",
            adr_id=adr_id,
            title=f"Decision for {title}",
            statement=decision,
            rationale=context,
            invariants=consequences
        )
        db.create_node(dec_id, "Decision", dec_node.model_dump())
        db.create_edge(adr_id, Relationships.DOCUMENTS_DECISION, dec_id)

        db.flush()
        return {
            "status": "INGESTED",
            "adr_id": adr_id,
            "title": title
        }
