"""
Graph Schema definitions for CodeGraph.
Implements the 4-Pillar Connected Knowledge Graph architecture anchored by Project:
1. CodeBase:   Project -> CodeInput -> LogicFlow -> Class -> Function -> CodeLogic -> CodeOutput
2. PRD:        Project -> PRDInput -> FunctionalRequirement -> Guardrail -> PRDOutput
3. ADR:        Project -> ADRRequirement -> Architecture -> Decision -> ADRResult
4. Operations: Project -> Issue -> RCA -> Fix -> OpResult
5. History & Timeline: ChangeTimeline tracking what changed and why it changed.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Root Anchor Node
# -------------------------------------------------------------

class ProjectNode(BaseModel):
    id: str  # e.g. "project:payflow"
    name: str  # e.g. "PayFlow Payment Gateway"
    description: str
    repository: str = "https://github.com/payflow/payflow-core"
    created_at: str = "2025-10-01"


# File and document artifact models
class FileNode(BaseModel):
    path: str
    language: str = "python"
    last_modified: Optional[float] = None


class PRDNode(BaseModel):
    id: str
    title: str
    version: str = "1.0"
    author: Optional[str] = None
    status: str = "APPROVED"
    created_at: Optional[str] = None


class ADRNode(BaseModel):
    id: str
    title: str
    status: str = "ACCEPTED"
    date: str
    context: str
    decision: str
    consequences: str


class BugFixNode(BaseModel):
    id: str
    ticket: str
    symptom: str
    description: str
    rca: str
    fix_summary: str
    approved: bool = True
    date: str


class RunbookNode(BaseModel):
    id: str
    title: str
    service: str
    symptom: str
    rca: str
    resolution_steps: str


class ScenarioNode(BaseModel):
    id: str
    req_id: str
    description: str
    expected_behavior: str
    covered_by_code: bool = True


class RequirementNode(BaseModel):
    id: str
    prd_id: str
    title: str
    description: str
    priority: str = "MEDIUM"
    status: str = "IMPLEMENTED"


class ChangeRecordNode(BaseModel):
    commit_hash: str
    author: str
    date: str
    message: str
    reason: str
    reason_id: Optional[str] = None
    file_path: str



# -------------------------------------------------------------
# 1. CodeBase Entity Chain Nodes
# project -> input -> logic flow -> classes -> functions -> code logic -> output
# -------------------------------------------------------------

class CodeInputNode(BaseModel):
    id: str  # e.g. "code_input:auth_args"
    project_id: str
    name: str
    parameter_signature: str
    source_type: str = "HTTP_BODY"
    description: str


class LogicFlowNode(BaseModel):
    id: str  # e.g. "flow:payment_auth"
    code_input_id: str
    name: str
    description: str
    steps: List[str] = Field(default_factory=list)


class ClassNode(BaseModel):
    id: str  # e.g. "class:PaymentService"
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None


class FunctionNode(BaseModel):
    id: str  # e.g. "func:validate_card"
    name: str
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    file_path: str
    signature: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None


class CodeLogicNode(BaseModel):
    id: str  # e.g. "logic:luhn_expiry_check"
    func_id: str
    name: str
    logic_type: str  # "VALIDATION", "RETRY_LOOP", "QUEUE_CONCURRENCY", "IDEMPOTENCY"
    code_snippet: str
    invariants: Optional[str] = None


class CodeOutputNode(BaseModel):
    id: str  # e.g. "code_output:auth_success_dict"
    logic_id: str
    name: str
    return_type: str = "Dict[str, Any]"
    sample_payload: str


# -------------------------------------------------------------
# 2. PRD Entity Chain Nodes
# project -> input -> functional requirements -> guardrails -> output
# -------------------------------------------------------------

class PRDInputNode(BaseModel):
    id: str  # e.g. "prd_input:checkout_request"
    project_id: str
    title: str
    business_payload: str
    actor: str = "Customer / Merchant"


class FunctionalRequirementNode(BaseModel):
    id: str  # e.g. "req:REQ-001"
    prd_input_id: str
    title: str
    description: str
    priority: str = "CRITICAL"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    status: str = "IMPLEMENTED"  # "IMPLEMENTED", "PENDING_DEV"


class GuardrailNode(BaseModel):
    id: str  # e.g. "guardrail:expiry_and_luhn"
    req_id: str
    title: str
    rule_statement: str
    enforcement_level: str = "HARD_BLOCK"  # "HARD_BLOCK", "CHALLENGE_3DS", "LOG_ONLY"
    violation_code: str


class PRDOutputNode(BaseModel):
    id: str  # e.g. "prd_output:card_expired_error"
    guardrail_id: str
    expected_status: str  # "SUCCESS", "REJECTED", "PROCESSING"
    business_outcome: str


# -------------------------------------------------------------
# 3. ADR Entity Chain Nodes
# project -> requirement -> architecture -> decisions -> result
# -------------------------------------------------------------

class ADRRequirementNode(BaseModel):
    id: str  # e.g. "adr_req:external_network_resilience"
    project_id: str
    title: str
    technical_driver: str


class ArchitectureNode(BaseModel):
    id: str  # e.g. "arch:exponential_backoff_pipeline"
    adr_req_id: str
    pattern_name: str
    description: str


class DecisionNode(BaseModel):
    id: str  # e.g. "decision:ADR-001:retry_ceiling"
    arch_id: str = "arch:default"
    adr_id: str  # e.g. "ADR-001"
    title: str = "Architectural Decision"
    statement: str
    rationale: str
    invariants: str = ""


class ADRResultNode(BaseModel):
    id: str  # e.g. "adr_result:98_pct_drop_reduction"
    decision_id: str
    positive_impact: str
    tradeoffs: str


# -------------------------------------------------------------
# 4. Operations Entity Chain Nodes
# project -> issues -> rca -> fix -> result
# -------------------------------------------------------------

class IssueNode(BaseModel):
    id: str  # e.g. "issue:BUG-342"
    project_id: str
    ticket: str
    title: str
    symptom: str
    severity: str = "CRITICAL"
    reported_at: str


class RCANode(BaseModel):
    id: str  # e.g. "rca:BUG-342:concurrency_reduction"
    issue_id: str
    root_cause: str
    trigger_condition: str


class FixNode(BaseModel):
    id: str  # e.g. "fix:BUG-342:restore_concurrency_5"
    rca_id: str
    action_taken: str
    commit_hash: str
    approved_by: str
    approval_status: str = "APPROVED"  # "APPROVED", "PENDING_APPROVAL"


class OpResultNode(BaseModel):
    id: str  # e.g. "op_result:BUG-342:lag_eliminated"
    fix_id: str
    verified_outcome: str
    verified_at: str


# -------------------------------------------------------------
# 5. History & Timeline Node (What & Why Lineage)
# -------------------------------------------------------------

class ChangeTimelineNode(BaseModel):
    id: str  # e.g. "timeline:commit:b7c8d9e"
    project_id: str
    commit_hash: str
    author: str
    timestamp: str
    date: str
    what_changed: str
    why_changed: str
    change_category: str  # "PRD_FEATURE", "ADR_ENFORCEMENT", "OPERATION_FIX", "REFACTOR"
    diff_summary: str


# -------------------------------------------------------------
# Typed Relationships (Edges)
# -------------------------------------------------------------

class Relationships:
    # --- 1. CodeBase Chain ---
    HAS_CODE_INPUT = "HAS_CODE_INPUT"              # (Project) -> (CodeInput)
    TRIGGERS_FLOW = "TRIGGERS_FLOW"                # (CodeInput) -> (LogicFlow)
    ROUTED_TO_CLASS = "ROUTED_TO_CLASS"            # (LogicFlow) -> (Class)
    CONTAINS_FUNCTION = "CONTAINS_FUNCTION"        # (Class) -> (Function)
    EXECUTES_LOGIC = "EXECUTES_LOGIC"              # (Function) -> (CodeLogic)
    PRODUCES_CODE_OUTPUT = "PRODUCES_CODE_OUTPUT"  # (CodeLogic) -> (CodeOutput)
    CALLS = "CALLS"                                # (Function) -> (Function)

    # --- 2. PRD Chain ---
    HAS_PRD_INPUT = "HAS_PRD_INPUT"                # (Project) -> (PRDInput)
    SPECIFIES_REQUIREMENT = "SPECIFIES_REQUIREMENT" # (PRDInput) -> (FunctionalRequirement)
    ENFORCES_GUARDRAIL = "ENFORCES_GUARDRAIL"      # (FunctionalRequirement) -> (Guardrail)
    DEFINES_PRD_OUTPUT = "DEFINES_PRD_OUTPUT"      # (Guardrail) -> (PRDOutput)

    # --- 3. ADR Chain ---
    HAS_ADR_REQUIREMENT = "HAS_ADR_REQUIREMENT"    # (Project) -> (ADRRequirement)
    DEFINES_ARCHITECTURE = "DEFINES_ARCHITECTURE"  # (ADRRequirement) -> (Architecture)
    LEADS_TO_DECISION = "LEADS_TO_DECISION"        # (Architecture) -> (Decision)
    YIELDS_RESULT = "YIELDS_RESULT"                # (Decision) -> (ADRResult)

    # --- 4. Operations Chain ---
    HAS_ISSUE = "HAS_ISSUE"                        # (Project) -> (Issue)
    ANALYZED_BY_RCA = "ANALYZED_BY_RCA"            # (Issue) -> (RCA)
    RESOLVED_BY_FIX = "RESOLVED_BY_FIX"            # (RCA) -> (Fix)
    ACHIEVES_RESULT = "ACHIEVES_RESULT"            # (Fix) -> (OpResult)

    # --- Cross-Entity Interlinks ---
    # PRD -> ADR (PRD drives architectural requirements)
    DRIVES_ADR_REQUIREMENT = "DRIVES_ADR_REQUIREMENT" # (FunctionalRequirement) -> (ADRRequirement)
    JUSTIFIES_DECISION = "JUSTIFIES_DECISION"         # (Guardrail) -> (Decision)
    CORRESPONDS_TO_ADR = "CORRESPONDS_TO_ADR"         # (PRDOutput) -> (ADRResult)

    # ADR -> CodeBase (Code built from ADR)
    CONSTRAINS_FUNCTION = "CONSTRAINS_FUNCTION"       # (Decision) -> (Function)
    ENFORCED_IN_CODE_LOGIC = "ENFORCED_IN_CODE_LOGIC" # (Decision) -> (CodeLogic)
    STRUCTURES_LOGIC_FLOW = "STRUCTURES_LOGIC_FLOW"   # (Architecture) -> (LogicFlow)

    # PRD -> CodeBase (Requirements implemented by code)
    MAPS_TO_CODE_INPUT = "MAPS_TO_CODE_INPUT"         # (PRDInput) -> (CodeInput)
    IMPLEMENTED_BY_FUNCTION = "IMPLEMENTED_BY_FUNCTION" # (FunctionalRequirement) -> (Function)
    VERIFIED_BY_LOGIC = "VERIFIED_BY_LOGIC"           # (Guardrail) -> (CodeLogic)
    EXPECTS_CODE_OUTPUT = "EXPECTS_CODE_OUTPUT"       # (PRDOutput) -> (CodeOutput)

    # Operations -> CodeBase / ADR / PRD (Operational fixes done for codebase)
    MANIFESTED_IN_FUNCTION = "MANIFESTED_IN_FUNCTION" # (Issue) -> (Function)
    VIOLATED_DECISION = "VIOLATED_DECISION"           # (Issue) -> (Decision)
    IMPACTED_REQUIREMENT = "IMPACTED_REQUIREMENT"     # (Issue) -> (FunctionalRequirement)
    FIXES_FUNCTION = "FIXES_FUNCTION"                 # (Fix) -> (Function)
    MODIFIES_CODE_LOGIC = "MODIFIES_CODE_LOGIC"       # (Fix) -> (CodeLogic)
    RESTORES_DECISION = "RESTORES_DECISION"           # (Fix) -> (Decision)

    # --- History and Timeline Lineage ---
    CHANGED_NODE = "CHANGED_NODE"                     # (ChangeTimeline) -> (CodeLogic | Function | Decision)
    MOTIVATED_BY_PRD = "MOTIVATED_BY_PRD"             # (ChangeTimeline) -> (FunctionalRequirement)
    MOTIVATED_BY_ADR = "MOTIVATED_BY_ADR"             # (ChangeTimeline) -> (Decision)
    MOTIVATED_BY_FIX = "MOTIVATED_BY_FIX"             # (ChangeTimeline) -> (Fix)
    PRECEDED_BY = "PRECEDED_BY"                       # (ChangeTimeline) -> (ChangeTimeline)

    # --- Compatibility & Convenience Aliases ---
    CONTAINS_CLASS = "ROUTED_TO_CLASS"
    CONTAINS_FUNC = "CONTAINS_FUNCTION"
    CLASS_METHOD = "CONTAINS_FUNCTION"
    CONTAINS_REQ = "SPECIFIES_REQUIREMENT"
    HAS_SCENARIO = "ENFORCES_GUARDRAIL"
    DOCUMENTS_DECISION = "LEADS_TO_DECISION"
    RESOLVES_BUG = "RESOLVED_BY_FIX"
    CHANGED_BY = "CHANGED_NODE"
    IMPLEMENTS_PRD = "IMPLEMENTED_BY_FUNCTION"
    VALIDATES_SCENARIO = "VERIFIED_BY_LOGIC"


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
