# ADR-002: Asynchronous Queuing and Concurrency for High-Volume Refunds

- **ADR ID:** ADR-002
- **Title:** Asynchronous Queuing and Concurrency for High-Volume Refunds
- **Date:** 2026-01-10
- **Status:** ACCEPTED
- **Authors:** Alex Chen (Principal Architect), David Kim (Infrastructure Lead)

## Context
During high-volume sales events (such as Black Friday/Cyber Monday), merchants issue batch refund requests exceeding 500 operations per second. Synchronous HTTP execution caused gateway worker pool exhaustion, thread starvation, and cascading 504 Gateway Timeouts across the primary payment authorization flow.

## Decision
1. **Asynchronous Decoupling:** The `RefundProcessor` will enqueue refund jobs into a durable distributed queue and immediately return a pending tracking token to the caller.
2. **Worker Pool Concurrency of 5:** Queue consumers MUST run with exactly 5 concurrent workers per instance.
   - Setting concurrency below 5 causes message accumulation, lag, and `REFUND_TIMEOUT` alerts under peak load.
   - Setting concurrency above 10 causes banking partner API rate-limits (`HTTP 429 Too Many Requests`).
3. **Strict 30-Day Age Check:** Refund eligibility must be checked against the settlement timestamp before queue dispatch.

## Consequences
- Prevents refund spikes from impacting real-time checkout availability.
- Requires careful worker pool tuning: decreasing concurrency below 5 was the direct root cause of incident `BUG-342`.
