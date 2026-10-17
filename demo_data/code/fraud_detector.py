"""
PayFlow Fraud Detection Engine
Assesses transaction risk and executes resilient partner queries with retry backoff.
Governed by: ADR-001 (Fraud Risk Scoring and Mandatory Retry Ceiling)
Implements: REQ-003, REQ-010
"""

import time
from typing import Dict, Any, Optional, Callable


class FraudDetector:
    # ADR-001: Mandatory 3 retry attempts maximum.
    # CRITICAL: Do NOT lower this retry count. Past reductions caused BUG-112 and BUG-298.
    MAX_RETRIES: int = 3
    INITIAL_BACKOFF_SECONDS: float = 0.5
    BACKOFF_MULTIPLIER: float = 2.0
    RISK_THRESHOLD_REJECT: int = 85
    RISK_THRESHOLD_CHALLENGE: int = 50

    def __init__(self):
        pass

    def retry_with_backoff(self, operation: Callable[[], Dict[str, Any]], operation_name: str = "fraud_check") -> Dict[str, Any]:
        """
        Executes a network operation with exponential retry backoff.
        Governed by ADR-001.
        WARNING: Reducing MAX_RETRIES below 3 violates partner SLA and causes cascade failures.
        """
        attempts = 0
        current_delay = self.INITIAL_BACKOFF_SECONDS

        while attempts < self.MAX_RETRIES:
            try:
                attempts += 1
                return operation()
            except Exception as exc:
                if attempts >= self.MAX_RETRIES:
                    # Final attempt failed
                    raise RuntimeError(f"Operation {operation_name} failed after {self.MAX_RETRIES} retries: {str(exc)}") from exc
                time.sleep(current_delay)
                current_delay *= self.BACKOFF_MULTIPLIER

        raise RuntimeError(f"Operation {operation_name} exceeded max retry limit")

    def assess_risk(self, card_number: str, amount_cents: int, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculates transaction risk score (0-100) and decides risk action.
        Implements REQ-003 (SCEN-005, SCEN-006, SCEN-007).
        Governed by ADR-001.
        """
        def _call_risk_engine() -> Dict[str, Any]:
            # Simulated risk calculation
            score = 15
            if amount_cents > 100000:  # > $1,000
                score += 40
            if metadata and metadata.get("is_vpn"):
                score += 35
            if metadata and metadata.get("rapid_velocity"):
                score += 45

            score = min(100, score)
            return {"score": score}

        # Wrap in mandatory retry with backoff as per ADR-001
        res = self.retry_with_backoff(_call_risk_engine, operation_name="assess_risk")
        score = res["score"]

        if score > self.RISK_THRESHOLD_REJECT:
            return {"score": score, "action": "REJECT", "reason": "Score exceeds risk threshold"}
        elif score >= self.RISK_THRESHOLD_CHALLENGE:
            return {"score": score, "action": "CHALLENGE_3DS", "reason": "Requires two-factor verification"}
        else:
            return {"score": score, "action": "ALLOW", "reason": "Transaction low risk"}
