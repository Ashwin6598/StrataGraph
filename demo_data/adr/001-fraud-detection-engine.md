# ADR-001: Fraud Risk Scoring and Mandatory Retry Ceiling

- **ADR ID:** ADR-001
- **Title:** Fraud Risk Scoring and Mandatory Retry Ceiling
- **Date:** 2025-11-20
- **Status:** ACCEPTED
- **Authors:** Alex Chen (Principal Architect), Marcus Vance (Lead Security Engineer)

## Context
Payment processing systems must evaluate high-risk signals in real time while maintaining resilient connections to external risk and clearing networks. During initial tests, unstable network segments caused random drops. Developers attempted to either bypass risk evaluation under latency or reduce retry attempts to 1, causing thousands of legitimate card transactions to fail.

## Decision
1. **Mandatory 3-Retry Ceiling:** Every external fraud evaluation and network call MUST execute exactly 3 retry attempts with exponential backoff (initial delay: 0.5s, factor: 2.0).
2. **Hard-Reject Boundary:** Any risk assessment resulting in a score strictly greater than 85 MUST trigger an immediate, non-overridable `FRAUD_RISK_REJECTED` error.
3. **Never Lower Retries:** Developers are explicitly forbidden from lowering the retry count below 3 or suppressing backoff delays, as this violates our card-scheme service level agreement (SLA).

## Consequences
- **Positive:** Reduces transaction false-drop rate by 98.4% during upstream jitter.
- **Negative:** Adds up to 3.5 seconds of worst-case latency during complete partner outages before failing over.
- **Critical Risk:** Modifying `retry_with_backoff` without cross-functional approval historically caused `BUG-112` and `BUG-298`.
