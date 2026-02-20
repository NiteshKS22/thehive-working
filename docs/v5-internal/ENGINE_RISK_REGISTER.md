# Engine Risk Register (v5)

## Critical Risks

### Risk-017: State Divergence (v4 vs v5)

**Description:** Due to asynchronous replication, v5 state may drift from v4 (system of record).
**Impact:** High. User confusion (cases not synced, outdated status).
**Mitigation:**
1.  Use `GREATEST(updated_at)` logic for idempotent writes.
2.  Implement Nightly Drift Detection Job.
3.  Log all conflicts to `bridge.drift.log`.
4.  Provide a manual "Resync Case" endpoint.

### Risk-018: Event Forgery via Bridge

**Description:** Malicious actors could inject events into bridge topics to modify v5 state, bypassing v4 auth.
**Impact:** Critical. Unauthorized data access/modification.
**Mitigation:**
1.  **mTLS:** All bridge services must communicate over mTLS.
2.  **AuthContext:** Bridge services run as trusted system components but validate tenant IDs against existing resources.
3.  **Audit:** All sync events are audited.
