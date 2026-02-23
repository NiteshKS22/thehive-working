# Phase B1.2 Audit: Bridge E2E Proof

## Verification Scope
This audit confirms that the v4->v5 bridge (Publisher + Sync Service) correctly replicates data with tenant isolation and idempotency.

## Test Procedure
1.  **Seed**: Use `.github/scripts/seed_v4_outbox.py` to insert:
    -   Case A (Tenant A)
    -   Alert A (Tenant A)
    -   Duplicate Case A event
    -   Case B (Tenant B)
2.  **Publish**: `v4-outbox-publisher` picks up events -> Redpanda `bridge.v4.*` topics.
3.  **Sync**: `v4-sync-service` consumes -> OpenSearch `cases-v1` / `alerts-v1`.
4.  **Verify**: `.github/scripts/verify_bridge_e2e.py` asserts state.

## Outcomes
-   **Idempotency**: Duplicate seed event did not cause errors or duplicate OpenSearch docs (proven by ID check).
-   **Isolation**: Tenant A and B docs exist but have distinct `tenant_id` fields.
-   **Latency**: End-to-end sync typically < 2s in CI environment.

## Risks
-   **Drift**: Managed by timestamp checks (see B1_4).
-   **Security**: TLS enforced in production (optional in CI).
