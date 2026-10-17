"""
Graph Schema definitions for CodeGraph.
Represents Nodes (Code, PRD, ADR, ChangeRecord, BugFix, Runbook) and their Relationships.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Node Models
# -------------------------------------------------------------

class PRDNode(BaseModel):
    id: str
    title: str
    version: str = "1.0"
    author: Optional[str] = None
    status: str = "APPROVED"
    created_at: Optional[str] = None


class RequirementNode(BaseModel):
    id: str
    prd_id: str
    title: str
    description: str
    priority: str = "MEDIUM"
    status: str = "IMPLEMENTED"  # "IMPLEMENTED", "PENDING_DEV", "DEPRECATED"


class ScenarioNode(BaseModel):
    id: str
    req_id: str
    description: str
    expected_behavior: str
    covered_by_code: bool = True


class ADRNode(BaseModel):
    id: str
    title: str
    status: str = "ACCEPTED"  # "ACCEPTED", "SUPERSEDED", "PROPOSED"
    date: str
    context: str
    decision: str
    consequences: str


class DecisionNode(BaseModel):
    id: str
    adr_id: str
    statement: str
    rationale: str
    rule_type: str = "ARCHITECTURAL_CONSTRAINT"


class FileNode(BaseModel):
    path: str
    language: str = "python"
    last_modified: Optional[float] = None


class ClassNode(BaseModel):
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None


class FunctionNode(BaseModel):
    name: str
    file_path: str
    signature: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    class_name: Optional[str] = None


class ChangeRecordNode(BaseModel):
    commit_hash: str
    author: str
    date: str
    message: str
    reason: str  # "PRD_REQUIREMENT", "ADR_ENFORCEMENT", "BUG_FIX", "REFACTOR"
    reason_id: Optional[str] = None  # e.g. "REQ-001", "ADR-001", "BUG-342"
    file_path: str


class BugFixNode(BaseModel):
    id: str  # e.g. "BUG-342"
    ticket: str
    symptom: str
    description: str
    rca: str
    fix_summary: str
    approved: bool = True
    date: str


class RunbookNode(BaseModel):
    id: str  # e.g. "RB-PAY-001"
    title: str
    service: str
    symptom: str
    rca: str
    resolution_steps: str


# -------------------------------------------------------------
# Relationship (Edge) Constants
# -------------------------------------------------------------

class Relationships:
    # PRD hierarchy
    CONTAINS_REQ = "CONTAINS_REQ"        # (PRD)-[:CONTAINS_REQ]->(Requirement)
    HAS_SCENARIO = "HAS_SCENARIO"        # (Requirement)-[:HAS_SCENARIO]->(Scenario)
    IMPLEMENTED_BY = "IMPLEMENTED_BY"    # (Requirement)-[:IMPLEMENTED_BY]->(Function)

    # ADR hierarchy
    DOCUMENTS_DECISION = "DOCUMENTS_DECISION"  # (ADR)-[:DOCUMENTS_DECISION]->(Decision)
    AFFECTS = "AFFECTS"                        # (Decision)-[:AFFECTS]->(Function)
    RELATES_TO = "RELATES_TO"                  # (ADR)-[:RELATES_TO]->(Requirement)

    # Code AST hierarchy
    CONTAINS_CLASS = "CONTAINS_CLASS"    # (File)-[:CONTAINS_CLASS]->(Class)
    CONTAINS_FUNC = "CONTAINS_FUNC"      # (File)-[:CONTAINS_FUNC]->(Function)
    CLASS_METHOD = "CLASS_METHOD"        # (Class)-[:CLASS_METHOD]->(Function)
    CALLS = "CALLS"                      # (Function)-[:CALLS]->(Function)

    # History & Quality Lineage
    CHANGED_BY = "CHANGED_BY"            # (Function)-[:CHANGED_BY]->(ChangeRecord)
    FIXED_BY = "FIXED_BY"                # (BugFix)-[:FIXED_BY]->(ChangeRecord)
    FIXED_IN = "FIXED_IN"                # (BugFix)-[:FIXED_IN]->(Function)
    DOCUMENTS = "DOCUMENTS"              # (Runbook)-[:DOCUMENTS]->(Function)
    RESOLVES_BUG = "RESOLVES_BUG"        # (Runbook)-[:RESOLVES_BUG]->(BugFix)


# -------------------------------------------------------------
# Query & Result Containers
# -------------------------------------------------------------

class TraversalStep(BaseModel):
    from_node: str
    relationship: str
    to_node: str
    explanation: Optional[str] = None


class ExplainableResult(BaseModel):
    result: Any
    cypher_query: str
    traversal_path: List[TraversalStep] = Field(default_factory=list)
    explanation: str
