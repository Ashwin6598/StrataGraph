"""
CodeGraph Seeding Script.
Builds the 4-Pillar Connected Knowledge Graph architecture anchored by Project:
  CodeBase:   Project -> Input -> Logic Flow -> Classes -> Functions -> Code Logic -> Output
  PRD:        Project -> Input -> Functional Requirements -> Guardrails -> Output
  ADR:        Project -> Requirement -> Architecture -> Decisions -> Result
  Operations: Project -> Issues -> RCA -> Fix -> Result
  Timeline:   ChangeTimeline capturing What was changed and Why it was changed.
"""

from codegraph.db import db
from codegraph.schema import (
    ProjectNode,
    CodeInputNode, LogicFlowNode, ClassNode, FunctionNode, CodeLogicNode, CodeOutputNode,
    PRDInputNode, FunctionalRequirementNode, GuardrailNode, PRDOutputNode,
    ADRRequirementNode, ArchitectureNode, DecisionNode, ADRResultNode,
    IssueNode, RCANode, FixNode, OpResultNode,
    ChangeTimelineNode,
    Relationships
)


def seed_all():
    print("🚀 Initializing CodeGraph Seeding (4-Pillar Architecture)...")
    db.clear()

    # =========================================================================
    # 0. Root Project Anchor
    # =========================================================================
    project_id = "project:payflow"
    project = ProjectNode(
        id=project_id,
        name="PayFlow Payment Gateway",
        description="Enterprise payment orchestration platform handling card authorizations, fraud analysis, and asynchronous refunds.",
        repository="https://github.com/payflow/payflow-core",
        created_at="2025-10-01",
        codebase_owner="payment-tech-lead@payflow.internal",
        prd_owner="product-lead@payflow.internal"
    )
    db.create_node(project_id, "Project", project.model_dump())
    print(f"📦 Created Root Project: {project.name}")

    # =========================================================================
    # 1. PRD Entity Chain: Project -> Input -> Requirements -> Guardrails -> Output
    # =========================================================================
    print("📄 Building PRD Entity Chain...")

    # PRD Inputs
    prd_inputs = [
        PRDInputNode(
            id="prd_input:checkout_payload",
            project_id=project_id,
            title="Customer Checkout Payment Request",
            business_payload="order_id, amount_cents, currency, card_number, expiry_month, expiry_year, idempotency_key",
            actor="E-Commerce Shopper"
        ),
        PRDInputNode(
            id="prd_input:refund_request",
            project_id=project_id,
            title="Merchant Refund Request",
            business_payload="order_id, amount_cents, settled_timestamp",
            actor="Merchant Admin"
        )
    ]
    for pi in prd_inputs:
        db.create_node(pi.id, "PRDInput", pi.model_dump())
        db.create_edge(project_id, Relationships.HAS_PRD_INPUT, pi.id)

    # Functional Requirements
    reqs = [
        FunctionalRequirementNode(
            id="req:REQ-001",
            prd_input_id="prd_input:checkout_payload",
            title="Card Payment Authorization",
            description="Authorize payment transactions securely with tokenized card details and enforce transaction limits.",
            priority="CRITICAL",
            status="IMPLEMENTED"
        ),
        FunctionalRequirementNode(
            id="req:REQ-002",
            prd_input_id="prd_input:checkout_payload",
            title="Expiry & Luhn Card Validation",
            description="Validate card expiration date and Luhn checksum before forwarding to external payment rails.",
            priority="CRITICAL",
            status="IMPLEMENTED"
        ),
        FunctionalRequirementNode(
            id="req:REQ-003",
            prd_input_id="prd_input:checkout_payload",
            title="Real-Time ML Fraud Risk Assessment",
            description="Evaluate transaction risk score between 0 and 100 before capturing charges.",
            priority="HIGH",
            status="IMPLEMENTED"
        ),
        FunctionalRequirementNode(
            id="req:REQ-004",
            prd_input_id="prd_input:checkout_payload",
            title="Multi-Currency Dynamic Currency Conversion (DCC)",
            description="Allow cross-border buyers to pay in their local home currency with dynamic FX spread calculation.",
            priority="MEDIUM",
            status="PENDING_DEV"
        ),
        FunctionalRequirementNode(
            id="req:REQ-005",
            prd_input_id="prd_input:checkout_payload",
            title="Idempotent Payment Submission",
            description="Repeated requests with duplicate Idempotency-Key return cached results without double charging.",
            priority="HIGH",
            status="IMPLEMENTED"
        ),
        FunctionalRequirementNode(
            id="req:REQ-006",
            prd_input_id="prd_input:checkout_payload",
            title="Asynchronous Webhook Event Delivery",
            description="Dispatch signed JSON webhooks to merchant endpoints upon status transitions.",
            priority="HIGH",
            status="IMPLEMENTED"
        ),
        FunctionalRequirementNode(
            id="req:REQ-007",
            prd_input_id="prd_input:refund_request",
            title="Full Refund Processing with 30-Day Window",
            description="Issue 100% full refunds against settled transactions within 30 days of the original settlement date.",
            priority="HIGH",
            status="IMPLEMENTED"
        ),
        FunctionalRequirementNode(
            id="req:REQ-008",
            prd_input_id="prd_input:refund_request",
            title="Partial Refund Support",
            description="Allow merchants to refund arbitrary line items or portions up to the remaining unrefunded balance.",
            priority="LOW",
            status="PENDING_DEV"
        ),
        FunctionalRequirementNode(
            id="req:REQ-010",
            prd_input_id="prd_input:checkout_payload",
            title="High-Concurrency Rate Limiting & Retry Backoff",
            description="Throttle downstream requests to avoid partner 429 rejections using exponential backoff.",
            priority="HIGH",
            status="IMPLEMENTED"
        )
    ]
    for r in reqs:
        db.create_node(r.id, "FunctionalRequirement", r.model_dump())
        db.create_edge(r.prd_input_id, Relationships.SPECIFIES_REQUIREMENT, r.id)

    # Guardrails
    guardrails = [
        GuardrailNode(
            id="guardrail:card_luhn_and_expiry",
            req_id="req:REQ-002",
            title="Card Expiration and Luhn Validity Guardrail",
            rule_statement="Card expiration year/month must be >= current date AND Luhn mod-10 checksum == 0.",
            enforcement_level="HARD_BLOCK",
            violation_code="CARD_EXPIRED"
        ),
        GuardrailNode(
            id="guardrail:fraud_score_ceiling_85",
            req_id="req:REQ-003",
            title="Fraud Score Upper Ceiling Guardrail",
            rule_statement="Transactions with risk score strictly greater than 85 MUST be hard rejected immediately.",
            enforcement_level="HARD_BLOCK",
            violation_code="FRAUD_RISK_REJECTED"
        ),
        GuardrailNode(
            id="guardrail:refund_30_day_limit",
            req_id="req:REQ-007",
            title="Refund 30-Day Settlement Window Guardrail",
            rule_statement="Refund requests where (current_time - settled_timestamp) > 30 days MUST be rejected.",
            enforcement_level="HARD_BLOCK",
            violation_code="REFUND_WINDOW_EXPIRED"
        ),
        GuardrailNode(
            id="guardrail:idempotency_24h_window",
            req_id="req:REQ-005",
            title="Idempotency Cache Replay Guardrail",
            rule_statement="Duplicate idempotency key within 24 hours must replay cached authorization without recharging.",
            enforcement_level="HARD_BLOCK",
            violation_code="IDEMPOTENCY_REPLAY"
        )
    ]
    for g in guardrails:
        db.create_node(g.id, "Guardrail", g.model_dump())
        db.create_edge(g.req_id, Relationships.ENFORCES_GUARDRAIL, g.id)

    # PRD Outputs
    prd_outputs = [
        PRDOutputNode(
            id="prd_output:payment_authorized_success",
            guardrail_id="guardrail:card_luhn_and_expiry",
            expected_status="SUCCESS",
            business_outcome="Customer payment is authorized and transaction token is returned to merchant checkout."
        ),
        PRDOutputNode(
            id="prd_output:card_expired_rejection",
            guardrail_id="guardrail:card_luhn_and_expiry",
            expected_status="REJECTED",
            business_outcome="Customer sees 'Card has expired' message with zero partner clearing fees incurred."
        ),
        PRDOutputNode(
            id="prd_output:refund_queued_processing",
            guardrail_id="guardrail:refund_30_day_limit",
            expected_status="PROCESSING",
            business_outcome="Merchant receives instant pending refund receipt while batch queue handles settlement."
        ),
        PRDOutputNode(
            id="prd_output:refund_expired_rejection",
            guardrail_id="guardrail:refund_30_day_limit",
            expected_status="REJECTED",
            business_outcome="Refund rejected with REFUND_WINDOW_EXPIRED error code."
        )
    ]
    for po in prd_outputs:
        db.create_node(po.id, "PRDOutput", po.model_dump())
        db.create_edge(po.guardrail_id, Relationships.DEFINES_PRD_OUTPUT, po.id)

    # =========================================================================
    # 2. ADR Entity Chain: Project -> Requirement -> Architecture -> Decisions -> Result
    # =========================================================================
    print("🏛️ Building ADR Entity Chain...")

    adr_reqs = [
        ADRRequirementNode(
            id="adr_req:external_network_resilience",
            project_id=project_id,
            title="External Risk Network Resilience and Zero False-Drop SLA",
            technical_driver="Third-party clearing networks experience 1-2% momentary packet drops during peak hours. Dropping requests causes merchant revenue loss."
        ),
        ADRRequirementNode(
            id="adr_req:peak_refund_throughput",
            project_id=project_id,
            title="High-Volume Batch Refund Isolation and Rate-Limit Protection",
            technical_driver="High-volume sales events trigger spikes of 500+ refunds/sec. Synchronous execution exhausts gateway thread pools."
        )
    ]
    for ar in adr_reqs:
        db.create_node(ar.id, "ADRRequirement", ar.model_dump())
        db.create_edge(project_id, Relationships.HAS_ADR_REQUIREMENT, ar.id)

    architectures = [
        ArchitectureNode(
            id="arch:resilient_retry_pipeline",
            adr_req_id="adr_req:external_network_resilience",
            pattern_name="Resilient Exponential Backoff and Circuit Breaker Pipeline",
            description="Wraps all external fraud scoring and bank network communications in an isolated retry loop with strict backoff ceilings."
        ),
        ArchitectureNode(
            id="arch:async_worker_queue",
            adr_req_id="adr_req:peak_refund_throughput",
            pattern_name="Decoupled Distributed Queue with Concurrency-Capped Consumers",
            description="Asynchronously enqueues refund jobs to isolate the checkout API while capping worker concurrency to respect banking partner rate limits."
        )
    ]
    for a in architectures:
        db.create_node(a.id, "Architecture", a.model_dump())
        db.create_edge(a.adr_req_id, Relationships.DEFINES_ARCHITECTURE, a.id)

    decisions = [
        DecisionNode(
            id="decision:ADR-001:retry_ceiling",
            arch_id="arch:resilient_retry_pipeline",
            adr_id="ADR-001",
            title="Mandatory 3-Retry Ceiling with Exponential Backoff",
            statement="Every external fraud evaluation and network call MUST execute exactly 3 retry attempts with exponential backoff (0.5s initial, 2.0x factor). Score > 85 is hard-rejected. Lowering retry count below 3 is strictly prohibited.",
            rationale="Eliminates false declines caused by momentary packet loss while avoiding cascade timeout loops.",
            invariants="MAX_RETRIES == 3, INITIAL_BACKOFF == 0.5s, RISK_THRESHOLD_REJECT == 85"
        ),
        DecisionNode(
            id="decision:ADR-002:concurrency_5",
            arch_id="arch:async_worker_queue",
            adr_id="ADR-002",
            title="Worker Pool Concurrency of 5 for High-Volume Refunds",
            statement="Queue consumers MUST run with exactly 5 concurrent workers per instance. Concurrency < 5 causes message accumulation and REFUND_TIMEOUT under load. Concurrency > 10 causes banking partner HTTP 429 rate limit errors.",
            rationale="Preserves checkout gateway thread availability while staying within bank clearing rate limits.",
            invariants="WORKER_POOL_CONCURRENCY == 5, MAX_REFUND_AGE_DAYS == 30"
        )
    ]
    for d in decisions:
        db.create_node(d.id, "Decision", d.model_dump())
        db.create_edge(d.arch_id, Relationships.LEADS_TO_DECISION, d.id)

    adr_results = [
        ADRResultNode(
            id="adr_result:98_pct_drop_reduction",
            decision_id="decision:ADR-001:retry_ceiling",
            positive_impact="Reduces transaction false-drop rate by 98.4% during upstream network jitter.",
            tradeoffs="Adds up to 3.5s worst-case latency during complete partner outages."
        ),
        ADRResultNode(
            id="adr_result:thread_starvation_eliminated",
            decision_id="decision:ADR-002:concurrency_5",
            positive_impact="Eliminates HTTP 504 Gateway Timeouts on primary payment authorization during Black Friday refund spikes.",
            tradeoffs="Refunds settle asynchronously rather than synchronously in-band."
        )
    ]
    for ar_res in adr_results:
        db.create_node(ar_res.id, "ADRResult", ar_res.model_dump())
        db.create_edge(ar_res.decision_id, Relationships.YIELDS_RESULT, ar_res.id)

    # =========================================================================
    # 3. CodeBase Entity Chain: Project -> Input -> Logic Flow -> Classes -> Functions -> Code Logic -> Output
    # =========================================================================
    print("💻 Building CodeBase Entity Chain...")

    code_inputs = [
        CodeInputNode(
            id="code_input:auth_args",
            project_id=project_id,
            name="PaymentService.authorize_payment Parameters",
            parameter_signature="(order_id: str, amount_cents: int, card_number: str, expiry_month: int, expiry_year: int, idempotency_key: str)",
            source_type="HTTP_JSON_PAYLOAD",
            description="Normalized authorization arguments extracted from customer payment request."
        ),
        CodeInputNode(
            id="code_input:refund_args",
            project_id=project_id,
            name="RefundProcessor.execute_refund Parameters",
            parameter_signature="(order_id: str, amount_cents: int, settled_timestamp: float)",
            source_type="HTTP_JSON_PAYLOAD",
            description="Refund request parameters extracted from merchant portal request."
        )
    ]
    for ci in code_inputs:
        db.create_node(ci.id, "CodeInput", ci.model_dump())
        db.create_edge(project_id, Relationships.HAS_CODE_INPUT, ci.id)

    logic_flows = [
        LogicFlowNode(
            id="flow:payment_authorization",
            code_input_id="code_input:auth_args",
            name="Payment Authorization Orchestration Flow",
            description="Validates card checksum & expiry -> scores fraud risk -> generates charge token -> dispatches webhook.",
            steps=["validate_card", "assess_risk", "create_charge_token", "send_webhook"]
        ),
        LogicFlowNode(
            id="flow:refund_execution",
            code_input_id="code_input:refund_args",
            name="Asynchronous Refund Execution Flow",
            description="Checks 30-day settlement window -> enqueues async worker job -> returns tracking receipt.",
            steps=["validate_refund_eligibility", "queue_refund_job", "send_webhook"]
        )
    ]
    for lf in logic_flows:
        db.create_node(lf.id, "LogicFlow", lf.model_dump())
        db.create_edge(lf.code_input_id, Relationships.TRIGGERS_FLOW, lf.id)

    classes = [
        ClassNode(
            id="class:PaymentService",
            name="PaymentService",
            file_path="demo_data/code/payment_service.py",
            line_start=12,
            line_end=95,
            docstring="Handles card validation, idempotency checks, fraud evaluation, and charge creation."
        ),
        ClassNode(
            id="class:FraudDetector",
            name="FraudDetector",
            file_path="demo_data/code/fraud_detector.py",
            line_start=12,
            line_end=68,
            docstring="Assesses transaction risk and executes resilient partner queries with retry backoff."
        ),
        ClassNode(
            id="class:RefundProcessor",
            name="RefundProcessor",
            file_path="demo_data/code/refund_processor.py",
            line_start=12,
            line_end=85,
            docstring="Manages refund validation, async queue dispatch, and settlement."
        ),
        ClassNode(
            id="class:NotificationService",
            name="NotificationService",
            file_path="demo_data/code/notification_service.py",
            line_start=9,
            line_end=40,
            docstring="Dispatches webhooks and receipts for transaction events."
        )
    ]
    for c in classes:
        db.create_node(c.id, "Class", c.model_dump())

    db.create_edge("flow:payment_authorization", Relationships.ROUTED_TO_CLASS, "class:PaymentService")
    db.create_edge("flow:payment_authorization", Relationships.ROUTED_TO_CLASS, "class:FraudDetector")
    db.create_edge("flow:refund_execution", Relationships.ROUTED_TO_CLASS, "class:RefundProcessor")

    functions = [
        FunctionNode(
            id="func:validate_card",
            name="validate_card",
            class_id="class:PaymentService",
            file_path="demo_data/code/payment_service.py",
            signature="validate_card(card_number, expiry_month, expiry_year)",
            line_start=20,
            line_end=48,
            docstring="Validates card structure, expiration date, and Luhn checksum."
        ),
        FunctionNode(
            id="func:authorize_payment",
            name="authorize_payment",
            class_id="class:PaymentService",
            file_path="demo_data/code/payment_service.py",
            signature="authorize_payment(order_id, amount_cents, card_number, expiry_month, expiry_year, idempotency_key, user_metadata)",
            line_start=50,
            line_end=94,
            docstring="Main entry point for authorizing customer charge."
        ),
        FunctionNode(
            id="func:assess_risk",
            name="assess_risk",
            class_id="class:FraudDetector",
            file_path="demo_data/code/fraud_detector.py",
            signature="assess_risk(card_number, amount_cents, metadata)",
            line_start=45,
            line_end=68,
            docstring="Calculates transaction risk score and decides risk action."
        ),
        FunctionNode(
            id="func:retry_with_backoff",
            name="retry_with_backoff",
            class_id="class:FraudDetector",
            file_path="demo_data/code/fraud_detector.py",
            signature="retry_with_backoff(operation, operation_name)",
            line_start=24,
            line_end=44,
            docstring="Executes a network operation with exponential retry backoff per ADR-001."
        ),
        FunctionNode(
            id="func:validate_refund_eligibility",
            name="validate_refund_eligibility",
            class_id="class:RefundProcessor",
            file_path="demo_data/code/refund_processor.py",
            signature="validate_refund_eligibility(settled_timestamp)",
            line_start=22,
            line_end=40,
            docstring="Validates whether transaction falls within the 30-day refund window."
        ),
        FunctionNode(
            id="func:queue_refund_job",
            name="queue_refund_job",
            class_id="class:RefundProcessor",
            file_path="demo_data/code/refund_processor.py",
            signature="queue_refund_job(order_id, amount_cents, settled_timestamp)",
            line_start=42,
            line_end=56,
            docstring="Enqueues refund into async queue governed by ADR-002."
        ),
        FunctionNode(
            id="func:execute_refund",
            name="execute_refund",
            class_id="class:RefundProcessor",
            file_path="demo_data/code/refund_processor.py",
            signature="execute_refund(order_id, amount_cents, settled_timestamp)",
            line_start=58,
            line_end=84,
            docstring="Executes full refund for an order."
        ),
        FunctionNode(
            id="func:send_webhook",
            name="send_webhook",
            class_id="class:NotificationService",
            file_path="demo_data/code/notification_service.py",
            signature="send_webhook(event_type, payload)",
            line_start=15,
            line_end=28,
            docstring="Dispatches signed webhook event to registered merchant endpoints."
        )
    ]
    for fn in functions:
        db.create_node(fn.id, "Function", fn.model_dump())
        if fn.class_id:
            db.create_edge(fn.class_id, Relationships.CONTAINS_FUNCTION, fn.id)

    # Function Calls
    db.create_edge("func:authorize_payment", Relationships.CALLS, "func:validate_card")
    db.create_edge("func:authorize_payment", Relationships.CALLS, "func:assess_risk")
    db.create_edge("func:authorize_payment", Relationships.CALLS, "func:send_webhook")
    db.create_edge("func:assess_risk", Relationships.CALLS, "func:retry_with_backoff")
    db.create_edge("func:execute_refund", Relationships.CALLS, "func:validate_refund_eligibility")
    db.create_edge("func:execute_refund", Relationships.CALLS, "func:queue_refund_job")
    db.create_edge("func:execute_refund", Relationships.CALLS, "func:send_webhook")

    code_logics = [
        CodeLogicNode(
            id="logic:luhn_and_expiry_check",
            func_id="func:validate_card",
            name="Luhn Checksum and Expiry Arithmetic Check",
            logic_type="VALIDATION",
            code_snippet="if expiry_year < current_year or (expiry_year == current_year and expiry_month < current_month): return CARD_EXPIRED; checksum % 10 == 0",
            invariants="Expiry year/month checked before network call"
        ),
        CodeLogicNode(
            id="logic:retry_exponential_backoff",
            func_id="func:retry_with_backoff",
            name="Exponential Backoff Loop with Fixed Ceiling of 3",
            logic_type="RETRY_LOOP",
            code_snippet="while attempts < self.MAX_RETRIES (3): try: return op() except: time.sleep(delay); delay *= 2.0",
            invariants="MAX_RETRIES == 3, INITIAL_DELAY == 0.5s"
        ),
        CodeLogicNode(
            id="logic:worker_concurrency_5",
            func_id="func:queue_refund_job",
            name="Worker Queue Concurrency Throttling",
            logic_type="QUEUE_CONCURRENCY",
            code_snippet="job = {'concurrency_limit': self.WORKER_POOL_CONCURRENCY (5)}; self.refund_queue.append(job)",
            invariants="WORKER_POOL_CONCURRENCY == 5"
        ),
        CodeLogicNode(
            id="logic:refund_age_30_days",
            func_id="func:validate_refund_eligibility",
            name="30-Day Settlement Date Boundary Validation",
            logic_type="VALIDATION",
            code_snippet="if (time.time() - settled_timestamp) / 86400 > 30: return REFUND_WINDOW_EXPIRED",
            invariants="MAX_REFUND_AGE_DAYS == 30"
        )
    ]
    for cl in code_logics:
        db.create_node(cl.id, "CodeLogic", cl.model_dump())
        db.create_edge(cl.func_id, Relationships.EXECUTES_LOGIC, cl.id)

    code_outputs = [
        CodeOutputNode(
            id="code_output:auth_success_dict",
            logic_id="logic:luhn_and_expiry_check",
            name="Authorization Success Response",
            return_type="Dict[str, Any]",
            sample_payload="{'status': 'SUCCESS', 'transaction_id': 'txn_101', 'amount_cents': 5000}"
        ),
        CodeOutputNode(
            id="code_output:card_expired_dict",
            logic_id="logic:luhn_and_expiry_check",
            name="Card Expired Error Response",
            return_type="Dict[str, Any]",
            sample_payload="{'status': 'REJECTED', 'error_code': 'CARD_EXPIRED', 'message': 'Card has expired'}"
        ),
        CodeOutputNode(
            id="code_output:refund_processing_dict",
            logic_id="logic:worker_concurrency_5",
            name="Refund Processing Acknowledgment",
            return_type="Dict[str, Any]",
            sample_payload="{'status': 'PROCESSING', 'refund_job_id': 'rfjob_4521_123', 'amount_refunded_cents': 2500}"
        )
    ]
    for co in code_outputs:
        db.create_node(co.id, "CodeOutput", co.model_dump())
        db.create_edge(co.logic_id, Relationships.PRODUCES_CODE_OUTPUT, co.id)

    # =========================================================================
    # 4. Operations Entity Chain: Project -> Issues -> RCA -> Fix -> Result
    # =========================================================================
    print("🚨 Building Operations Entity Chain...")

    issues = [
        IssueNode(
            id="issue:BUG-342",
            project_id=project_id,
            ticket="BUG-342",
            title="REFUND_TIMEOUT on /v1/refunds during Black Friday peak load",
            symptom="REFUND_TIMEOUT, HTTP 504 Gateway Timeout on /v1/refunds endpoint, queue consumer lag > 120s",
            severity="CRITICAL",
            reported_at="2026-02-15"
        ),
        IssueNode(
            id="issue:BUG-112",
            project_id=project_id,
            ticket="BUG-112",
            title="Spike in legitimate card decline errors during network jitter",
            symptom="FRAUD_SERVICE_UNAVAILABLE, sudden 2% drop in authorized transactions",
            severity="HIGH",
            reported_at="2026-01-04"
        ),
        IssueNode(
            id="issue:BUG-298",
            project_id=project_id,
            ticket="BUG-298",
            title="Downstream clearing partner rate limit 429 flood",
            symptom="HTTP 429 Too Many Requests from banking partner",
            severity="HIGH",
            reported_at="2026-01-20"
        )
    ]
    for iss in issues:
        db.create_node(iss.id, "Issue", iss.model_dump())
        db.create_edge(project_id, Relationships.HAS_ISSUE, iss.id)

    rcas = [
        RCANode(
            id="rca:BUG-342:concurrency_reduction",
            issue_id="issue:BUG-342",
            root_cause="RefundProcessor.WORKER_POOL_CONCURRENCY was accidentally reduced from 5 to 2 in a hotfix PR. At concurrency 2, consumer queue became saturated at >80 req/s, queue lag exceeded gateway timeout limit.",
            trigger_condition="Refund request volume exceeded 80 requests/second under holiday peak load."
        ),
        RCANode(
            id="rca:BUG-112:retry_lowered_to_1",
            issue_id="issue:BUG-112",
            root_cause="A junior developer reduced MAX_RETRIES from 3 to 1 in fraud_detector.py to speed up checkout responses. Removing retry attempts caused 1 out of 50 legitimate checkouts to fail on momentary packet drops.",
            trigger_condition="Upstream clearing partner experienced 1-2% momentary packet loss."
        )
    ]
    for rc in rcas:
        db.create_node(rc.id, "RCA", rc.model_dump())
        db.create_edge(rc.issue_id, Relationships.ANALYZED_BY_RCA, rc.id)

    fixes = [
        FixNode(
            id="fix:BUG-342:restore_concurrency_5",
            rca_id="rca:BUG-342:concurrency_reduction",
            action_taken="Restored WORKER_POOL_CONCURRENCY to 5 in refund_processor.py as strictly mandated by ADR-002.",
            commit_hash="b7c8d9e0f1",
            approved_by="david.infra@payflow.internal",
            approval_status="APPROVED"
        ),
        FixNode(
            id="fix:BUG-112:restore_retries_3",
            rca_id="rca:BUG-112:retry_lowered_to_1",
            action_taken="Restored MAX_RETRIES = 3 and INITIAL_BACKOFF_SECONDS = 0.5 per ADR-001.",
            commit_hash="f1e2d3c4b5",
            approved_by="marcus.sec@payflow.internal",
            approval_status="APPROVED"
        )
    ]
    for fx in fixes:
        db.create_node(fx.id, "Fix", fx.model_dump())
        db.create_edge(fx.rca_id, Relationships.RESOLVED_BY_FIX, fx.id)

    op_results = [
        OpResultNode(
            id="op_result:BUG-342:lag_cleared",
            fix_id="fix:BUG-342:restore_concurrency_5",
            verified_outcome="Queue consumer lag dropped from 120s to <0.4s. 504 timeouts eliminated and 500+ refunds/sec sustained.",
            verified_at="2026-02-18"
        ),
        OpResultNode(
            id="op_result:BUG-112:declines_normalized",
            fix_id="fix:BUG-112:restore_retries_3",
            verified_outcome="False decline rate dropped from 2.0% back to baseline <0.01% with zero impact to checkout availability.",
            verified_at="2026-01-05"
        )
    ]
    for opr in op_results:
        db.create_node(opr.id, "OpResult", opr.model_dump())
        db.create_edge(opr.fix_id, Relationships.ACHIEVES_RESULT, opr.id)

    # =========================================================================
    # 5. History and Timeline Layer (What Changed & Why)
    # =========================================================================
    print("📜 Building Change History & Timeline Lineage...")

    timelines = [
        ChangeTimelineNode(
            id="timeline:commit:a1b2c3d",
            project_id=project_id,
            commit_hash="a1b2c3d4e5",
            author="sarah.dev@payflow.internal",
            timestamp="2025-10-15T09:15:00Z",
            date="2025-10-15",
            what_changed="Implemented initial card validation & Luhn checksum algorithm in payment_service.py",
            why_changed="Fulfills PRD requirement REQ-002: Expiry & Luhn Card Validation",
            change_category="PRD_FEATURE",
            diff_summary="def validate_card(...): checksum % 10 == 0; expiry_year < current_year"
        ),
        ChangeTimelineNode(
            id="timeline:commit:e4f5a6b",
            project_id=project_id,
            commit_hash="e4f5a6b7c8",
            author="alex.arch@payflow.internal",
            timestamp="2025-11-22T14:30:00Z",
            date="2025-11-22",
            what_changed="Enforced ADR-001 mandatory 3-retry ceiling with exponential backoff in fraud_detector.py",
            why_changed="Architectural mandate ADR-001 to prevent partner network jitter false declines",
            change_category="ADR_ENFORCEMENT",
            diff_summary="MAX_RETRIES: int = 3; while attempts < self.MAX_RETRIES: ... delay *= 2.0"
        ),
        ChangeTimelineNode(
            id="timeline:commit:f1e2d3c",
            project_id=project_id,
            commit_hash="f1e2d3c4b5",
            author="marcus.sec@payflow.internal",
            timestamp="2026-01-05T11:45:00Z",
            date="2026-01-05",
            what_changed="Restored MAX_RETRIES = 3 in fraud_detector.py",
            why_changed="Resolves production incident BUG-112 where unauthorized reduction to 1 retry caused false card declines",
            change_category="OPERATION_FIX",
            diff_summary="MAX_RETRIES = 3  # Restored per ADR-001 to resolve BUG-112"
        ),
        ChangeTimelineNode(
            id="timeline:commit:b7c8d9e",
            project_id=project_id,
            commit_hash="b7c8d9e0f1",
            author="david.infra@payflow.internal",
            timestamp="2026-02-18T16:20:00Z",
            date="2026-02-18",
            what_changed="Restored WORKER_POOL_CONCURRENCY = 5 in refund_processor.py",
            why_changed="Resolves production incident BUG-342 REFUND_TIMEOUT caused by concurrency drop violating ADR-002",
            change_category="OPERATION_FIX",
            diff_summary="WORKER_POOL_CONCURRENCY = 5  # Restored per ADR-002 to resolve BUG-342"
        )
    ]
    for tl in timelines:
        db.create_node(tl.id, "ChangeTimeline", tl.model_dump())
        db.create_edge(project_id, "HAS_TIMELINE_RECORD", tl.id)

    # Link Timeline Chronologically: commit1 -> commit2 -> commit3 -> commit4
    db.create_edge("timeline:commit:a1b2c3d", Relationships.PRECEDED_BY, "timeline:commit:e4f5a6b")
    db.create_edge("timeline:commit:e4f5a6b", Relationships.PRECEDED_BY, "timeline:commit:f1e2d3c")
    db.create_edge("timeline:commit:f1e2d3c", Relationships.PRECEDED_BY, "timeline:commit:b7c8d9e")

    # =========================================================================
    # 6. Cross-Entity Interlinks (Bridging PRD <-> ADR <-> CodeBase <-> Operations)
    # =========================================================================
    print("🔗 Building Cross-Entity Interlinks...")

    # PRD -> ADR (PRD drives architectural requirements)
    db.create_edge("req:REQ-003", Relationships.DRIVES_ADR_REQUIREMENT, "adr_req:external_network_resilience")
    db.create_edge("req:REQ-010", Relationships.DRIVES_ADR_REQUIREMENT, "adr_req:external_network_resilience")
    db.create_edge("req:REQ-007", Relationships.DRIVES_ADR_REQUIREMENT, "adr_req:peak_refund_throughput")
    db.create_edge("guardrail:fraud_score_ceiling_85", Relationships.JUSTIFIES_DECISION, "decision:ADR-001:retry_ceiling")
    db.create_edge("guardrail:refund_30_day_limit", Relationships.JUSTIFIES_DECISION, "decision:ADR-002:concurrency_5")
    db.create_edge("prd_output:payment_authorized_success", Relationships.CORRESPONDS_TO_ADR, "adr_result:98_pct_drop_reduction")

    # ADR -> CodeBase (Code is built from ADR decisions)
    db.create_edge("decision:ADR-001:retry_ceiling", Relationships.CONSTRAINS_FUNCTION, "func:retry_with_backoff")
    db.create_edge("decision:ADR-001:retry_ceiling", Relationships.CONSTRAINS_FUNCTION, "func:assess_risk")
    db.create_edge("decision:ADR-001:retry_ceiling", Relationships.ENFORCED_IN_CODE_LOGIC, "logic:retry_exponential_backoff")
    db.create_edge("decision:ADR-002:concurrency_5", Relationships.CONSTRAINS_FUNCTION, "func:queue_refund_job")
    db.create_edge("decision:ADR-002:concurrency_5", Relationships.CONSTRAINS_FUNCTION, "func:execute_refund")
    db.create_edge("decision:ADR-002:concurrency_5", Relationships.ENFORCED_IN_CODE_LOGIC, "logic:worker_concurrency_5")
    db.create_edge("arch:resilient_retry_pipeline", Relationships.STRUCTURES_LOGIC_FLOW, "flow:payment_authorization")
    db.create_edge("arch:async_worker_queue", Relationships.STRUCTURES_LOGIC_FLOW, "flow:refund_execution")

    # PRD -> CodeBase (Requirements implemented by code functions and logic)
    db.create_edge("prd_input:checkout_payload", Relationships.MAPS_TO_CODE_INPUT, "code_input:auth_args")
    db.create_edge("prd_input:refund_request", Relationships.MAPS_TO_CODE_INPUT, "code_input:refund_args")
    db.create_edge("req:REQ-001", Relationships.IMPLEMENTED_BY_FUNCTION, "func:authorize_payment")
    db.create_edge("req:REQ-002", Relationships.IMPLEMENTED_BY_FUNCTION, "func:validate_card")
    db.create_edge("req:REQ-003", Relationships.IMPLEMENTED_BY_FUNCTION, "func:assess_risk")
    db.create_edge("req:REQ-005", Relationships.IMPLEMENTED_BY_FUNCTION, "func:authorize_payment")
    db.create_edge("req:REQ-006", Relationships.IMPLEMENTED_BY_FUNCTION, "func:send_webhook")
    db.create_edge("req:REQ-007", Relationships.IMPLEMENTED_BY_FUNCTION, "func:execute_refund")
    db.create_edge("req:REQ-007", Relationships.IMPLEMENTED_BY_FUNCTION, "func:validate_refund_eligibility")
    db.create_edge("req:REQ-010", Relationships.IMPLEMENTED_BY_FUNCTION, "func:retry_with_backoff")
    # Note: REQ-004 and REQ-008 intentionally have NO code links (PENDING_DEV)

    db.create_edge("guardrail:card_luhn_and_expiry", Relationships.VERIFIED_BY_LOGIC, "logic:luhn_and_expiry_check")
    db.create_edge("guardrail:fraud_score_ceiling_85", Relationships.VERIFIED_BY_LOGIC, "logic:retry_exponential_backoff")
    db.create_edge("guardrail:refund_30_day_limit", Relationships.VERIFIED_BY_LOGIC, "logic:refund_age_30_days")
    db.create_edge("prd_output:payment_authorized_success", Relationships.EXPECTS_CODE_OUTPUT, "code_output:auth_success_dict")
    db.create_edge("prd_output:card_expired_rejection", Relationships.EXPECTS_CODE_OUTPUT, "code_output:card_expired_dict")
    db.create_edge("prd_output:refund_queued_processing", Relationships.EXPECTS_CODE_OUTPUT, "code_output:refund_processing_dict")

    # Operations -> CodeBase / ADR / PRD (Operations fixes done for the codebase)
    db.create_edge("issue:BUG-342", Relationships.MANIFESTED_IN_FUNCTION, "func:queue_refund_job")
    db.create_edge("issue:BUG-342", Relationships.VIOLATED_DECISION, "decision:ADR-002:concurrency_5")
    db.create_edge("issue:BUG-342", Relationships.IMPACTED_REQUIREMENT, "req:REQ-007")
    db.create_edge("fix:BUG-342:restore_concurrency_5", Relationships.FIXES_FUNCTION, "func:queue_refund_job")
    db.create_edge("fix:BUG-342:restore_concurrency_5", Relationships.MODIFIES_CODE_LOGIC, "logic:worker_concurrency_5")
    db.create_edge("fix:BUG-342:restore_concurrency_5", Relationships.RESTORES_DECISION, "decision:ADR-002:concurrency_5")

    db.create_edge("issue:BUG-112", Relationships.MANIFESTED_IN_FUNCTION, "func:retry_with_backoff")
    db.create_edge("issue:BUG-112", Relationships.VIOLATED_DECISION, "decision:ADR-001:retry_ceiling")
    db.create_edge("issue:BUG-112", Relationships.IMPACTED_REQUIREMENT, "req:REQ-003")
    db.create_edge("fix:BUG-112:restore_retries_3", Relationships.FIXES_FUNCTION, "func:retry_with_backoff")
    db.create_edge("fix:BUG-112:restore_retries_3", Relationships.MODIFIES_CODE_LOGIC, "logic:retry_exponential_backoff")
    db.create_edge("fix:BUG-112:restore_retries_3", Relationships.RESTORES_DECISION, "decision:ADR-001:retry_ceiling")

    # Timeline Connections (What & Why Lineage)
    db.create_edge("timeline:commit:a1b2c3d", Relationships.CHANGED_NODE, "logic:luhn_and_expiry_check")
    db.create_edge("timeline:commit:a1b2c3d", Relationships.MOTIVATED_BY_PRD, "req:REQ-002")

    db.create_edge("timeline:commit:e4f5a6b", Relationships.CHANGED_NODE, "logic:retry_exponential_backoff")
    db.create_edge("timeline:commit:e4f5a6b", Relationships.MOTIVATED_BY_ADR, "decision:ADR-001:retry_ceiling")

    db.create_edge("timeline:commit:f1e2d3c", Relationships.CHANGED_NODE, "logic:retry_exponential_backoff")
    db.create_edge("timeline:commit:f1e2d3c", Relationships.MOTIVATED_BY_FIX, "fix:BUG-112:restore_retries_3")

    db.create_edge("timeline:commit:b7c8d9e", Relationships.CHANGED_NODE, "logic:worker_concurrency_5")
    db.create_edge("timeline:commit:b7c8d9e", Relationships.MOTIVATED_BY_FIX, "fix:BUG-342:restore_concurrency_5")

    db.flush()

    info = db.get_backend_info()
    print("\n✅ 4-Pillar Knowledge Graph Successfully Seeded!")
    print(f"   Backend: {info['backend']}")
    print(f"   Nodes: {len(db.memory_graph.nodes)}")
    print(f"   Edges: {len(db.memory_graph.edges)}")


if __name__ == "__main__":
    seed_all()
