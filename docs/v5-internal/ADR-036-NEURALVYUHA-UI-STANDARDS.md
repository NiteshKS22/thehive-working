# ADR-036: NeuralVyuha UI Component Standards

## Status
Accepted

## Context
With Phase E6.2, we are introducing new UI components ("NeuralVyuha Incidents") into the legacy AngularJS shell. These components interface directly with the new `nv-core` backend services via the `nv-query` API, bypassing the legacy monolith's data access layer.

## Decision
We define the following standards for all NeuralVyuha UI development:

1.  **Namespace Isolation**: All new Angular components (Controllers, Services, Directives) must be prefixed with `Nv` (e.g., `NvGroupListCtrl`, `NvApiSrv`).
2.  **API Access**:
    *   All HTTP calls to `nv-core` services must be routed through `NvApiSrv`.
    *   Use `NvConfig` for base URL configuration.
    *   Auth Token: Attempts to inject JWT from `AuthenticationSrv.currentUser.token` if available, otherwise relies on session cookies via proxy.
3.  **Error Handling**:
    *   "Fail Open": UI components should handle API unavailability gracefully (e.g., loading states, empty lists) without crashing the entire application.
    *   Use `NotificationSrv` for user feedback on 403 (Permission Denied) errors.
4.  **Routing**:
    *   New routes must be prefixed with `/nv/` (e.g., `/nv/incidents`).
    *   Use `ui-sref="app.nv-..."` for internal navigation.

## Consequences
*   **Decoupling**: UI components are loosely coupled to the backend implementation, allowing independent evolution of the `nv-core` API.
*   **Consistency**: A unified service (`NvApiSrv`) ensures consistent error handling and auth token management.
*   **Maintainability**: Clear separation of legacy code and new NeuralVyuha code via naming conventions.
