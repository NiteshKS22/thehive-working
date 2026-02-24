# Phase E6.1 Audit: UI Routing

## Routing Logic
-   **Service:** `NvRouter.js`
-   **Config:** `NvConfig.js`
-   **Flags:** `UI_USE_V5_QUERY_READS`, `UI_V5_FALLBACK_TO_V4`.

## Verification
-   **403:** Confirmed to fail-closed (no fallback).
-   **500/Timeout:** Confirmed to fail-open (fallback to v4).
-   **Isolation:** Auth header forwarded correctly.
