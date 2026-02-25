# ADR-038: Dual-Write & Reverse Sync Strategy

## Status
Accepted

## Context
Phase E6.4 marks the transition of the "Write Path" for Cases and Tasks from the legacy v4 monolith to the NeuralVyuha (NV) engine. To ensure zero downtime and maintain legacy system integrity during the cutover, we need a strategy that keeps v4 in sync with v5 without coupling the UI write performance to the legacy backend.

## Decision
We implement an **Asynchronous Reverse Sync** pattern:

1.  **Master of Record**: NeuralVyuha (NV) is now the authoritative source for new Cases and Tasks.
2.  **UI Writes**: The frontend writes directly to NV via `NvApiSrv`.
3.  **Reverse Bridge**: A dedicated worker service consumes NV domain events (e.g., `nv.cases.created.v1`) and replicates them to the legacy v4 API.
4.  **Panic Switch**: A configuration flag `NvConfig.MASTER_WRITE_TARGET` allows instant rollback to v4 writes if NV experiences critical failure.

## Consequences
*   **Performance**: UI interactions are decoupled from legacy system latency.
*   **Consistency**: There is a small replication lag (usually sub-second). The UI handles this by reading from NV immediately.
*   **Conflict Resolution**: If a case exists in v4 (e.g., created manually during migration), the Reverse Bridge attempts to link or update it, prioritizing NV state.
*   **Idempotency**: All writes must use `Idempotency-Key` to prevent duplication during network retries or replay.

## Governance
*   The legacy v4 database must contain a `v5_ref` custom field to store the NV Case UUID.
*   Updates from v4 to v5 (if any occur) must be handled by the existing Phase B1 Sync Service (bidirectional sync is now active but v5 is primary).
