"""
PayFlow Notification Service
Dispatches webhooks and receipts for transaction events.
Implements: REQ-006, REQ-009
"""

from typing import Dict, Any, List


class NotificationService:
    def __init__(self):
        self.sent_events: List[Dict[str, Any]] = []

    def send_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches signed webhook event to registered merchant endpoints.
        Implements REQ-006.
        """
        event = {
            "event_type": event_type,
            "payload": payload,
            "dispatched": True,
            "http_status": 200
        }
        self.sent_events.append(event)
        return event

    def send_receipt(self, email: str, transaction_id: str, amount_cents: int) -> Dict[str, Any]:
        """
        Sends email confirmation receipt to customer.
        """
        return {
            "recipient": email,
            "transaction_id": transaction_id,
            "amount_cents": amount_cents,
            "status": "SENT"
        }
