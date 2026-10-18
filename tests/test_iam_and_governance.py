"""
Unit and Integration Tests for IAM (RBAC) and Multi-Persona Governance Workflows.
Verifies:
1. Role-Based Access Control (RBAC) permission resolution and enforcement.
2. Program Manager persona creating Epics, Features, and Stories via agent tools.
3. IAM authorization guards rejecting unauthorized persona mutations.
4. Developer architectural proposal workflow (PENDING_APPROVAL, email dispatch to Architect).
5. Architect approval workflow via secure token and rejection of unauthorized approvers.
6. Direct Architect authoring workflow (immediate APPROVED status).
7. Project node architect_owner property integrity.
"""

import pytest
from codegraph.db import db
from codegraph.iam import iam, Role, Permission
from codegraph.schema import ProjectNode, Relationships
from codegraph.approval_service import SENT_APPROVAL_EMAILS, resolve_architect_owner
from codegraph.tools.program_tools import create_epic, create_feature, create_story
from codegraph.tools.product_tools import update_prd_features_and_scenarios
from codegraph.tools.ingest_tools import record_bugfix
from codegraph.tools.architect_tools import (
    propose_architectural_change,
    approve_architectural_proposal_via_email
)
from codegraph.mcp_server import check_iam_permission, list_iam_roles


@pytest.fixture(autouse=True)
def setup_test_graph():
    """Seeds the in-memory test graph with a clean PayFlow project node."""
    db.memory_graph.clear()
    SENT_APPROVAL_EMAILS.clear()

    project = ProjectNode(
        id="project:payflow",
        name="PayFlow Payment Gateway",
        description="Unified financial orchestration platform",
        codebase_owner="payment-tech-lead@payflow.internal",
        prd_owner="product-lead@payflow.internal",
        architect_owner="architect-lead@payflow.internal"
    )
    db.create_node("project:payflow", "Project", project.model_dump())
    db.flush()
    yield
    SENT_APPROVAL_EMAILS.clear()


# =========================================================================
# 1. IAM Role & Permission Matrix Tests
# =========================================================================

def test_iam_role_resolution():
    """Verify resolution of email addresses to designated roles."""
    assert iam.resolve_role("tpm-lead@payflow.internal") == Role.PROGRAM_MANAGER
    assert iam.resolve_role("product-lead@payflow.internal") == Role.PRODUCT_MANAGER
    assert iam.resolve_role("developer@payflow.internal") == Role.DEVELOPER
    assert iam.resolve_role("payment-tech-lead@payflow.internal") == Role.DEVELOPER
    assert iam.resolve_role("architect-lead@payflow.internal") == Role.ARCHITECT
    assert iam.resolve_role("admin@payflow.internal") == Role.ADMIN
    assert iam.resolve_role("unknown-user@payflow.internal") == Role.DEVELOPER


def test_iam_permission_checks():
    """Verify permission assignments per role."""
    # Program Manager
    assert iam.check_permission("tpm-lead@payflow.internal", Permission.MANAGE_AGILE_FLOW) is True
    assert iam.check_permission("tpm-lead@payflow.internal", Permission.UPDATE_PRD) is False
    assert iam.check_permission("tpm-lead@payflow.internal", Permission.MODIFY_CODEBASE) is False
    assert iam.check_permission("tpm-lead@payflow.internal", Permission.PROPOSE_ARCHITECTURE) is False

    # Product Manager
    assert iam.check_permission("product-lead@payflow.internal", Permission.UPDATE_PRD) is True
    assert iam.check_permission("product-lead@payflow.internal", Permission.MANAGE_AGILE_FLOW) is False
    assert iam.check_permission("product-lead@payflow.internal", Permission.MODIFY_CODEBASE) is False

    # Developer
    assert iam.check_permission("developer@payflow.internal", Permission.MODIFY_CODEBASE) is True
    assert iam.check_permission("developer@payflow.internal", Permission.PROPOSE_ARCHITECTURE) is True
    assert iam.check_permission("developer@payflow.internal", Permission.AUTHOR_ARCHITECTURE) is False
    assert iam.check_permission("developer@payflow.internal", Permission.MANAGE_AGILE_FLOW) is False

    # Architect
    assert iam.check_permission("architect-lead@payflow.internal", Permission.AUTHOR_ARCHITECTURE) is True
    assert iam.check_permission("architect-lead@payflow.internal", Permission.PROPOSE_ARCHITECTURE) is True
    assert iam.check_permission("architect-lead@payflow.internal", Permission.MANAGE_AGILE_FLOW) is False

    # Admin
    assert iam.check_permission("admin@payflow.internal", Permission.MANAGE_AGILE_FLOW) is True
    assert iam.check_permission("admin@payflow.internal", Permission.UPDATE_PRD) is True
    assert iam.check_permission("admin@payflow.internal", Permission.MODIFY_CODEBASE) is True
    assert iam.check_permission("admin@payflow.internal", Permission.AUTHOR_ARCHITECTURE) is True


# =========================================================================
# 2. Program Manager Agent Creation Tools & IAM Enforcement
# =========================================================================

def test_program_manager_can_create_epic():
    """Verify Program Manager can create an Epic and Developer is denied."""
    # Authorized: Program Manager
    res = create_epic(
        epic_key="PAY-EPIC-901",
        summary="Unified Tokenization Platform",
        description="Migrate card storage to zero-knowledge vault",
        actor="tpm-lead@payflow.internal"
    )
    assert res["result"]["status"] == "CREATED"
    assert res["result"]["epic_key"] == "PAY-EPIC-901"
    assert "epic:PAY-EPIC-901" in db.memory_graph.nodes

    # Denied: Developer attempting to create an Epic
    denied = create_epic(
        epic_key="PAY-EPIC-902",
        summary="Rogue Epic by Dev",
        actor="developer@payflow.internal"
    )
    assert denied["status"] == "PERMISSION_DENIED"
    assert denied["error_code"] == "IAM_ACCESS_DENIED"
    assert "epic:PAY-EPIC-902" not in db.memory_graph.nodes


def test_program_manager_can_create_feature_and_story():
    """Verify Program Manager can create Features and Stories with cross-links."""
    # 1. Create Epic
    create_epic(
        epic_key="PAY-EPIC-903",
        summary="Dispute Handling Automation",
        actor="tpm-lead@payflow.internal"
    )

    # 2. Create Feature under Epic
    feat_res = create_feature(
        feature_key="PAY-FEAT-903-A",
        epic_key_or_id="PAY-EPIC-903",
        summary="Automated Chargeback Evidence Packager",
        service_name="dispute_service",
        actor="tpm-lead@payflow.internal"
    )
    assert feat_res["result"]["status"] == "CREATED"
    assert "feat:PAY-FEAT-903-A" in db.memory_graph.nodes

    # 3. Create Story under Feature
    story_res = create_story(
        story_key="PAY-991",
        feature_key_or_id="PAY-FEAT-903-A",
        summary="Implement PDF evidence export",
        story_points=5,
        assignee="Bob Martinez",
        actor="tpm-lead@payflow.internal"
    )
    assert story_res["result"]["status"] == "CREATED"
    assert "story:PAY-991" in db.memory_graph.nodes

    # Verify edge connectivity in graph
    has_feature_edge = any(
        e["from"] == "epic:PAY-EPIC-903" and e["to"] == "feat:PAY-FEAT-903-A"
        for e in db.memory_graph.edges
    )
    assert has_feature_edge is True

    has_story_edge = any(
        e["from"] == "feat:PAY-FEAT-903-A" and e["to"] == "story:PAY-991"
        for e in db.memory_graph.edges
    )
    assert has_story_edge is True

    # Denied: Product Manager attempting to create a Story
    denied_story = create_story(
        story_key="PAY-992",
        feature_key_or_id="PAY-FEAT-903-A",
        summary="Unauthorized story",
        actor="product-lead@payflow.internal"
    )
    assert denied_story["status"] == "PERMISSION_DENIED"


# =========================================================================
# 3. Product Manager PRD Updates & Developer Codebase Guards
# =========================================================================

def test_prd_updates_guarded_by_iam():
    """Verify only Product Managers/Admins can update and approve PRD features and scenarios."""
    from codegraph.tools.product_tools import approve_prd_update_via_email

    # Authorized: Product Manager proposes feature
    res = update_prd_features_and_scenarios(
        feature_id="REQ-TEST-001",
        feature_title="Instant Bank Settlement",
        description="Support instant FedNow clearing",
        actor="product-lead@payflow.internal"
    )
    assert res["result"]["status"] == "PENDING_APPROVAL"
    token = res["result"]["approval_token"]

    # Denied: Developer trying to update PRD
    denied_update = update_prd_features_and_scenarios(
        feature_id="REQ-TEST-002",
        feature_title="Unauthorized PRD change",
        description="Dev altering requirements directly",
        actor="developer@payflow.internal"
    )
    assert denied_update["status"] == "PERMISSION_DENIED"
    assert denied_update["required_permission"] == "UPDATE_PRD"

    # Denied: Developer trying to approve PRD proposal
    denied_approval = approve_prd_update_via_email(
        feature_id="REQ-TEST-001",
        approval_token=token,
        approver_email="developer@payflow.internal"
    )
    assert denied_approval["status"] == "PERMISSION_DENIED"
    assert denied_approval["required_permission"] == "UPDATE_PRD"

    # Authorized: Product Manager approves PRD proposal
    approved = approve_prd_update_via_email(
        feature_id="REQ-TEST-001",
        approval_token=token,
        approver_email="product-lead@payflow.internal"
    )
    assert approved["result"]["status"] == "APPROVED"
    assert approved["result"]["approved_by"] == "product-lead@payflow.internal"


def test_codebase_modifications_guarded_by_iam():
    """Verify only Developers/Admins can record bugfixes and codebase changes."""
    # Authorized: Developer
    res = record_bugfix(
        ticket_id="BUG-TEST-001",
        symptom="Race condition on debit",
        rca="Missing Redis distributed lock",
        fix_summary="Added Redis mutex lock around transaction",
        affected_function_name="process_payment",
        actor="payment-tech-lead@payflow.internal"
    )
    assert res["result"]["status"] == "PENDING_APPROVAL"

    # Denied: Product Manager trying to record codebase bugfix
    denied = record_bugfix(
        ticket_id="BUG-TEST-002",
        symptom="Unauthorized code modification",
        rca="Product Manager changing code",
        fix_summary="Direct code overwrite",
        affected_function_name="process_payment",
        actor="product-lead@payflow.internal"
    )
    assert denied["status"] == "PERMISSION_DENIED"
    assert denied["required_permission"] == "MODIFY_CODEBASE"


# =========================================================================
# 4. Architectural Proposal & Approval Governance Tests
# =========================================================================

def test_developer_propose_architecture_dispatches_email_to_architect():
    """Verify Developer can propose architectural change, which requires Architect email approval."""
    res = propose_architectural_change(
        decision_id="ADR-099:kafka_idempotent_consumer",
        pattern_name="Event Sourcing with Idempotent Consumer",
        decision_statement="Consume settlement events using exactly-once semantics with transactional outbox.",
        rationale="Eliminates financial ledger discrepancies under network partitions.",
        invariants="Zero duplicate ledger postings; idempotency window >= 7 days",
        actor="developer@payflow.internal",
        approved_by_architect=False
    )

    result_data = res["result"]
    assert result_data["status"] == "PENDING_APPROVAL"
    assert result_data["approved"] is False
    assert result_data["proposed_by"] == "developer@payflow.internal"
    assert result_data["architect_owner"] == "architect-lead@payflow.internal"
    assert result_data["approval_token"] is not None
    assert result_data["email_dispatched"] is True

    # Verify email was recorded in outbox
    assert len(SENT_APPROVAL_EMAILS) == 1
    email = SENT_APPROVAL_EMAILS[0]
    assert email["to"] == "architect-lead@payflow.internal"
    assert "ADR-099:kafka_idempotent_consumer" in email["subject"]
    assert email["approval_token"] == result_data["approval_token"]

    # Verify Decision node in DB is PENDING_APPROVAL
    d_node = db.memory_graph.nodes.get("decision:ADR-099:kafka_idempotent_consumer")
    assert d_node is not None
    assert d_node["properties"]["status"] == "PENDING_APPROVAL"


def test_architect_approves_developer_proposal():
    """Verify Architect can approve developer proposal via token, while Developer approval is rejected."""
    # 1. Developer proposes change
    prop_res = propose_architectural_change(
        decision_id="ADR-100:circuit_breaker_threshold",
        pattern_name="Adaptive Circuit Breaker",
        decision_statement="Trip circuit when upstream gateway error rate exceeds 15% over 10 seconds.",
        rationale="Prevents cascading thread pool starvation across payment services.",
        invariants="Half-open trial requests capped at 3 requests every 10 seconds",
        actor="developer@payflow.internal"
    )
    token = prop_res["result"]["approval_token"]

    # 2. Developer attempts to self-approve proposal (Must be rejected by IAM)
    dev_approval = approve_architectural_proposal_via_email(
        decision_id="ADR-100:circuit_breaker_threshold",
        approval_token=token,
        actor="developer@payflow.internal"
    )
    assert dev_approval["status"] == "PERMISSION_DENIED"
    assert dev_approval["required_permission"] == "AUTHOR_ARCHITECTURE"

    # 3. Architect approves proposal (Authorized)
    arch_approval = approve_architectural_proposal_via_email(
        decision_id="ADR-100:circuit_breaker_threshold",
        approval_token=token,
        actor="architect-lead@payflow.internal"
    )
    assert arch_approval["result"]["status"] == "APPROVED"
    assert arch_approval["result"]["approved_by"] == "architect-lead@payflow.internal"

    # Verify node and edge status in graph
    d_node = db.memory_graph.nodes.get("decision:ADR-100:circuit_breaker_threshold")
    assert d_node["properties"]["status"] == "APPROVED"
    assert d_node["properties"]["approved_by"] == "architect-lead@payflow.internal"


def test_architect_direct_authoring_is_immediately_approved():
    """Verify Architect can directly author ADR without pending email approval gate."""
    res = propose_architectural_change(
        decision_id="ADR-101:global_multi_datacenter",
        pattern_name="Multi-Region Active-Active Sharding",
        decision_statement="Deploy multi-region CockroachDB clusters across US and EU zones.",
        rationale="Guarantees regulatory compliance with GDPR while achieving 99.999% availability.",
        invariants="Cross-region replication latency < 100ms",
        actor="architect-lead@payflow.internal",
        approved_by_architect=True
    )

    result_data = res["result"]
    assert result_data["status"] == "APPROVED"
    assert result_data["approved"] is True
    assert result_data["approval_token"] is None
    assert result_data["email_dispatched"] is False


def test_unauthorized_propose_architecture_denied():
    """Verify non-engineering roles (Product, Program) cannot propose architectural decisions."""
    denied_pm = propose_architectural_change(
        decision_id="ADR-102:unauthorized",
        pattern_name="Rogue Architecture",
        decision_statement="Direct DB writes bypassing microservices",
        rationale="Faster MVP delivery",
        actor="product-lead@payflow.internal"
    )
    assert denied_pm["status"] == "PERMISSION_DENIED"
    assert denied_pm["required_permission"] == "PROPOSE_ARCHITECTURE"


# =========================================================================
# 5. Project Node Architect Owner & MCP Introspection Tests
# =========================================================================

def test_project_architect_owner_resolution():
    """Verify ProjectNode contains architect_owner and resolves correctly."""
    owner = resolve_architect_owner("project:payflow")
    assert owner == "architect-lead@payflow.internal"


def test_mcp_iam_introspection_tools():
    """Verify MCP tools for IAM permissions and roles introspection."""
    # check_iam_permission
    tpm_check = check_iam_permission("tpm-lead@payflow.internal", "MANAGE_AGILE_FLOW")
    assert tpm_check["authorized"] is True
    assert tpm_check["resolved_role"] == "PROGRAM_MANAGER"

    dev_check = check_iam_permission("developer@payflow.internal", "AUTHOR_ARCHITECTURE")
    assert dev_check["authorized"] is False

    # list_iam_roles
    roles_info = list_iam_roles()
    assert "PROGRAM_MANAGER" in roles_info["roles_and_permissions"]
    assert "ARCHITECT" in roles_info["roles_and_permissions"]
    assert len(roles_info["registered_users"]) >= 5
