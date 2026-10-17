# Runbook RB-PAY-001: Triage and Resolution for Payment and Refund Timeouts

- **Runbook ID:** RB-PAY-001
- **Service:** PayFlow Payment & Refund Gateway
- **Audience:** On-Call Engineers & Senior Developers
- **Last Verified:** 2026-03-01

---

## 1. Incident: REFUND_TIMEOUT Under Load
- **Error Code / Symptom:** `REFUND_TIMEOUT`, `HTTP 504 Gateway Timeout` on `/v1/refunds` endpoint.
- **Historical Reference:** `BUG-342` (Black Friday incident).
- **Root Cause Analysis (RCA):**
  The `RefundProcessor.WORKER_POOL_CONCURRENCY` was accidentally reduced from 5 to 2 in a hotfix PR. At concurrency 2, the async consumer queue becomes saturated whenever request volume exceeds 80 refunds/sec. Messages queue up, consumer lag reaches >120s, and API gateways drop connections with `REFUND_TIMEOUT`.
- **Immediate Diagnostic Command:**
  Check queue depth and consumer concurrency in `refund_processor.py`.
- **Verified Resolution:**
  1. Open `demo_data/code/refund_processor.py`.
  2. Ensure `WORKER_POOL_CONCURRENCY` is set to `5` as specified in `ADR-002`.
  3. Restart worker pool service.
  4. Never set concurrency > 10 (triggers partner HTTP 429).

---

## 2. Incident: CASCADE_FRAUD_CHECK_FAILURES
- **Error Code / Symptom:** `FRAUD_SERVICE_UNAVAILABLE`, spikes in legitimate card declines.
- **Historical References:** `BUG-112`, `BUG-298`.
- **Root Cause Analysis (RCA):**
  A junior developer reduced `MAX_RETRIES` from 3 to 1 in `fraud_detector.py` to "speed up checkout responses". Because third-party credit card fraud networks experience 1-2% momentary packet drops, removing retry attempts caused 1 out of every 50 checkout requests to fail immediately.
- **Verified Resolution:**
  1. Refer to `ADR-001` (Fraud Risk Scoring and Mandatory Retry Ceiling).
  2. Restore `MAX_RETRIES = 3` and `INITIAL_BACKOFF_SECONDS = 0.5`.
  3. Run verification test suite.
