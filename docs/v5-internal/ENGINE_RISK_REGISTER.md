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

### Risk-019: Outbox Backlog Growth

**Description:** If the publisher fails or Redpanda is down, the `v4_outbox` table may grow indefinitely.
**Impact:** High. Storage exhaustion on v4 DB.
**Mitigation:**
1.  **Monitoring:** Alert on `outbox_backlog_total`.
2.  **Circuit Breaker:** Stop v4 writes if outbox full (optional, severe) OR auto-scale publisher.
3.  **Retention:** Prune PUBLISHED rows after X days.

### Risk-020: Bridge Event Forgery

**Description:** Malicious injection of events into bridge topics could corrupt v5.
**Impact:** Critical.
**Mitigation:**
1.  **ACLs:** Only `v4-outbox-publisher` can write to `bridge.*`.
2.  **TLS:** Strict mTLS enforcement (B1.1 requirement).

### Risk-021: Sync Loop Storms

**Description:** v4 updates trigger v5 sync, which triggers v5 writeback, which triggers v4 update...
**Impact:** High. System overload.
**Mitigation:**
1.  **Origin Markers:** v5 ignores events from . v4 outbox ignores changes made by applier.
2.  **Deduplication:** Inbox dedupe index prevents re-applying same event.

### Risk-022: Writeback Conflict Data Loss

**Description:** v5 overwrites a concurrent v4 user edit.
**Impact:** Medium. User frustration.
**Mitigation:**
1.  **Timestamps:** Writeback only applies if .
2.  **Audit:** All conflicts logged.

### Risk-021: Sync Loop Storms

**Description:** v4 updates trigger v5 sync, which triggers v5 writeback, which triggers v4 update...
**Impact:** High. System overload.
**Mitigation:**
1.  **Origin Markers:** v5 ignores events from `meta.origin='v4'`. v4 outbox ignores changes made by applier.
2.  **Deduplication:** Inbox dedupe index prevents re-applying same event.

### Risk-022: Writeback Conflict Data Loss

**Description:** v5 overwrites a concurrent v4 user edit.
**Impact:** Medium. User frustration.
**Mitigation:**
1.  **Timestamps:** Writeback only applies if `v5.updated_at > v4.updated_at`.
2.  **Audit:** All conflicts logged.
