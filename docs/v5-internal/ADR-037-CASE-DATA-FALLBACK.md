# ADR-037: Case Data Fallback & Consistency Policy

## Status
Accepted

## Context
Phase E6.3 migrates the Case and Task "Read-Path" to the NeuralVyuha (NV) backend. However, the NV backend is strictly decoupled from the v4 monolith and relies on the Phase B1 Sync Service to stay up-to-date. There is a risk of:
1.  **Latency:** NV might be slightly behind v4 due to async replication.
2.  **Incompleteness:** NV Case Service might not yet support all legacy fields (e.g., computed statistics like `taskStats`, `observableStats`).
3.  **Availability:** NV services are new and might be less stable than the LTS monolith.

## Decision
We implement a **"Fail-Safe Strangler Pattern"** for Case reads in the UI:

1.  **Primary Path:** The UI (`CaseSrv`) attempts to fetch data from the NV API (`NvApiSrv`) first.
2.  **Fallback Path:** If the NV API returns a 404 (Not Found) or 5xx (Error), the UI automatically falls back to the legacy v4 API (`QuerySrv`) without interrupting the user flow.
3.  **Data Mapping:** NV response objects are mapped to the legacy Schema on the client-side to ensure compatibility with existing AngularJS templates.
4.  **Transparency:** Cases served by the NV engine are marked with an "NV" badge in the UI. Cases served by v4 (fallback) have no badge.

## Consequences
*   **Reliability:** User experience is protected against NV instability.
*   **Visibility:** Analysts can see which engine is serving their data, aiding in trust-building and debugging.
*   **Stats Limitation:** If NV data is used, some computed stats (e.g., attachment counts) might be missing or zero until the NV backend implements deep aggregation. This is an accepted trade-off for E6.3 to validate the core read path.

## Governance
Any data drift detected (where NV returns stale data compared to v4) should be logged as a warning in the browser console for debugging but will not block the user.
