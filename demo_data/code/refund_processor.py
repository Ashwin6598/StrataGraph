"""
PayFlow Refund Processing Engine
Manages refund validation, async queue dispatch, and settlement.
Governed by: ADR-002 (Asynchronous Queuing and Concurrency for High-Volume Refunds)
Implements: REQ-007 (Full Refund Processing with 30-Day Window)
"""

import time
from typing import Dict, Any, Optional
from .notification_service import NotificationService


class RefundProcessor:
    # ADR-002: Queue worker pool concurrency MUST remain exactly 5.
    # Concurrency < 5 causes REFUND_TIMEOUT under load (BUG-342).
    # Concurrency > 10 causes banking partner HTTP 429 rate limit errors.
    WORKER_POOL_CONCURRENCY: int = 5
    MAX_REFUND_AGE_DAYS: int = 30

    def __init__(self, notifier: Optional[NotificationService] = None):
        self.notifier = notifier or NotificationService()
        self.refund_queue = []

    def validate_refund_eligibility(self, settled_timestamp: float) -> Dict[str, Any]:
        """
        Validates whether transaction falls within the 30-day refund window.
        Implements REQ-007 (SCEN-011, SCEN-012).
        """
        now = time.time()
        age_in_seconds = now - settled_timestamp
        age_in_days = age_in_seconds / (24 * 3600)

        if age_in_days > self.MAX_REFUND_AGE_DAYS:
            return {
                "eligible": False,
                "error_code": "REFUND_WINDOW_EXPIRED",
                "message": f"Transaction age ({age_in_days:.1f} days) exceeds the 30-day refund limit."
            }

        return {"eligible": True, "error_code": None, "message": "Eligible for refund"}

    def queue_refund_job(self, order_id: str, amount_cents: int, settled_timestamp: float) -> Dict[str, Any]:
        """
        Enqueues refund into async queue. Governed by ADR-002.
        """
        job_id = f"rfjob_{order_id}_{int(time.time())}"
        job = {
            "job_id": job_id,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "status": "QUEUED",
            "enqueued_at": time.time(),
            "concurrency_limit": self.WORKER_POOL_CONCURRENCY
        }
        self.refund_queue.append(job)
        return job

    def execute_refund(self, order_id: str, amount_cents: int, settled_timestamp: float) -> Dict[str, Any]:
        """
        Executes full refund for an order.
        Validates 30-day limit -> enqueues async job -> notifies merchant.
        """
        eligibility = self.validate_refund_eligibility(settled_timestamp)
        if not eligibility["eligible"]:
            return {
                "status": "REJECTED",
                "error_code": eligibility["error_code"],
                "message": eligibility["message"],
                "order_id": order_id
            }

        job = self.queue_refund_job(order_id, amount_cents, settled_timestamp)

        # Immediate async receipt
        result = {
            "status": "PROCESSING",
            "refund_job_id": job["job_id"],
            "order_id": order_id,
            "amount_refunded_cents": amount_cents,
            "message": "Refund enqueued for batch settlement."
        }
        self.notifier.send_webhook(event_type="refund.processed", payload=result)
        return result
