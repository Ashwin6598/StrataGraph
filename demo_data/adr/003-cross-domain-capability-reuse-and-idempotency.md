# ADR-003: Cross-Domain Capability Reuse and Distributed Idempotency

- **ADR ID:** ADR-003
- **Title:** Cross-Domain Capability Reuse and Distributed Idempotency
- **Date:** 2026-02-05
- **Status:** ACCEPTED
- **Authors:** Alex Chen (Principal Architect), Bob Martinez (Tech Lead)

## Context
As PayFlow expands to multi-currency operations (`fx_service`), partial refunds (`refund_processor`), and high-volume checkouts (`payment_service`), service teams faced delivery delays caused by duplicate engineering efforts and double-submission risks:
1. The incoming Dynamic Currency Conversion (DCC) integration requires communicating with European Central Bank (ECB) rate servers over the public internet with retry backoff.
2. The partial refund engine is susceptible to duplicate submissions under network latency, risking double payouts.
3. Teams were preparing to build isolated, duplicative retry wrappers and lock managers.

## Decision
1. **Mandatory Cross-Domain Pattern Reuse:**
   - Outbound financial HTTP integrations (such as `fx_service` connecting to ECB feeds) MUST reuse the proven 3-retry exponential backoff pipeline established in `fraud_detector` (`ADR-001`).
   - Teams are strictly forbidden from implementing custom HTTP retry loops.
2. **Distributed Redis Idempotency Key Standard:**
   - Any state-mutating payment or refund endpoint MUST acquire a distributed lock keyed on `Idempotency-Key` with a 120-second TTL.
   - `refund_processor` (`PAY-307`) must directly adopt the idempotency lock pattern verified by `payment_service` (`PAY-308`).
3. **Cross-Domain Knowledge Sharing:**
   - Technical Program Managers (TPMs) are authorized to connect engineers across domain boundaries whenever an unassigned or blocked story shares architectural patterns with an existing service.

## Consequences
- **Positive:**
  - Accelerates `fx_service` delivery by ~5-8 story points by eliminating custom network retry boilerplate.
  - Eliminates duplicate refund payouts and race conditions across distributed microservices.
  - Reduces total lines of code and maintenance overhead across services.
- **Negative:**
  - Requires cross-team awareness and adherence to shared architecture invariants.
