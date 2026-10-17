"""
PayFlow Payment Service
Handles card validation, idempotency checks, fraud evaluation, and charge creation.
Implements: REQ-001, REQ-002, REQ-005
"""

import time
from typing import Dict, Any, Optional
from .fraud_detector import FraudDetector
from .notification_service import NotificationService


class PaymentService:
    def __init__(self, fraud_detector: Optional[FraudDetector] = None, notifier: Optional[NotificationService] = None):
        self.fraud_detector = fraud_detector or FraudDetector()
        self.notifier = notifier or NotificationService()
        self.idempotency_cache: Dict[str, Dict[str, Any]] = {}

    def validate_card(self, card_number: str, expiry_month: int, expiry_year: int) -> Dict[str, Any]:
        """
        Validates card structure, expiration date, and Luhn checksum.
        Implements REQ-002 (SCEN-003, SCEN-004).
        """
        current_year = 2026
        current_month = 10

        if expiry_year < current_year or (expiry_year == current_year and expiry_month < current_month):
            return {"valid": False, "error_code": "CARD_EXPIRED", "message": "Card has expired"}

        cleaned = card_number.replace(" ", "").replace("-", "")
        if not cleaned.isdigit() or len(cleaned) < 13:
            return {"valid": False, "error_code": "INVALID_CARD_NUMBER", "message": "Card number format invalid"}

        # Luhn Algorithm Check
        digits = [int(d) for d in cleaned]
        checksum = 0
        reverse_digits = digits[::-1]
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = digit * 2
                checksum += doubled - 9 if doubled > 9 else doubled
            else:
                checksum += digit

        if checksum % 10 != 0:
            return {"valid": False, "error_code": "INVALID_CARD_NUMBER", "message": "Luhn check failed"}

        return {"valid": True, "error_code": None, "message": "Card validation passed"}

    def authorize_payment(
        self,
        order_id: str,
        amount_cents: int,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        idempotency_key: Optional[str] = None,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for authorizing a customer charge.
        Implements REQ-001, REQ-002, REQ-003, REQ-005.
        Calls validate_card -> assess_risk -> execute_charge -> send_webhook.
        """
        # Idempotency check (REQ-005)
        if idempotency_key and idempotency_key in self.idempotency_cache:
            cached = self.idempotency_cache[idempotency_key]
            return {"status": "SUCCESS", "cached": True, **cached}

        # Step 1: Pre-validation (REQ-002)
        val_result = self.validate_card(card_number, expiry_month, expiry_year)
        if not val_result["valid"]:
            return {
                "status": "REJECTED",
                "error_code": val_result["error_code"],
                "message": val_result["message"],
                "order_id": order_id
            }

        # Step 2: Fraud Risk Scoring (REQ-003 & ADR-001)
        risk_result = self.fraud_detector.assess_risk(card_number=card_number, amount_cents=amount_cents, metadata=user_metadata)
        if risk_result["action"] == "REJECT":
            return {
                "status": "FRAUD_REJECTED",
                "error_code": "FRAUD_RISK_REJECTED",
                "message": f"Fraud score {risk_result['score']} exceeds allowed limit",
                "order_id": order_id
            }

        # Step 3: Authorization Execution
        txn_id = f"txn_{order_id}_{int(time.time())}"
        response = {
            "status": "SUCCESS",
            "transaction_id": txn_id,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "authorized_at": time.time(),
            "risk_score": risk_result["score"]
        }

        if idempotency_key:
            self.idempotency_cache[idempotency_key] = response

        # Step 4: Dispatch Notification (REQ-006)
        self.notifier.send_webhook(event_type="payment.authorized", payload=response)
        return response
