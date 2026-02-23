# Phase B1.4 Runbook: Drift Detection

## Configuration
-   **Schedule:** Nightly at 02:00 UTC.
-   **Env Vars:**
    -   `V4_DB_DSN_SECRET`: Path to v4 secret.
    -   `OPENSEARCH_HOST`: v5 endpoint.

## Interpreting Reports
-   **Mismatch:** Hash differs. Check `updated_at`.
-   **Missing in v5:** Sync latency or failure.
-   **Missing in v4:** Orphaned v5 data (critical).

## Resolution
-   **Manual:** Use `nightly_drift_check.py --repair --case-id X` (future feature).
-   **Auto:** Currently disabled.
