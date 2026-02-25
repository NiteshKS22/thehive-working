# Phase E6.3 Audit: Case Read-Path Migration

## Objective
Redirect legacy Case List and Case Details views to read from NeuralVyuha services with safe fallback.

## Implemented Changes

### 1. Service Layer
*   **`NvApiSrv.js`**: Added `getCases`, `getCase`, `getCaseTimeline` methods.
*   **`CaseSrv.js`**:
    *   Added `NvCaseListAdapter` to mimic `PaginatedQuerySrv` interface.
    *   Replaced `new PaginatedQuerySrv` usage in `CaseListCtrl` with `CaseSrv.list`.
    *   Updated `getById` to try NV first, then fallback to legacy.

### 2. UI Controllers
*   **`CaseListCtrl.js`**: Updated to use `CaseSrv.list`.
*   **`CaseDetailsCtrl.js`**: Updated to fetch "Unified Timeline" from NV via `NvApiSrv`.

### 3. Templates
*   **`case.list.html`**: Added "NV" badge to case titles served by NeuralVyuha.
*   **`case.details.html`**:
    *   Added "NV" badge to case title.
    *   Added "Unified Timeline" section at the bottom of the details view.

## Verification
*   **Fallback Safety**: If `NvConfig.useNvQueryReads` is true but the service fails, the UI falls back to v4 automatically.
*   **Tenant Isolation**: JWT token is propagated via `NvApiSrv`.
*   **No Data Loss**: Legacy fields are mapped or fallback is used.
