# Phase E1 Auth Audit & Hardening Report

## CHECK A: DEV_MODE Privilege Escalation
- **STATUS**: BUG (Confirmed)
- **EVIDENCE**: Previous logic allowed header overrides unconditionally if `DEV_MODE=True`.
- **ACTION**: Implemented strict `DEV_MODE` logic.
    - Default safe context (dev-user/dev-tenant).
    - Only allow header overrides if explicitly running in DEV_MODE.
    - Added warning logs.
- **TEST**: `test_middleware.py::test_dev_mode_headers` verifies headers are accepted in dev mode but ignored in prod mode.

## CHECK B: JWT Claim Enforcement
- **STATUS**: BUG (Confirmed)
- **EVIDENCE**: Missing checks for `sub` and roles format (string vs list).
- **ACTION**: Added validation:
    - Reject token if `sub` or `tenant_id` is missing.
    - Normalize `roles` claim to always be a list (even if string).
- **TEST**: `test_middleware.py::test_missing_claims` and `test_roles_normalization`.

## CHECK C: RS256/OIDC Readiness
- **STATUS**: POTENTIAL BUG (Misconfiguration Risk)
- **EVIDENCE**: No check for public key presence if algorithm changed.
- **ACTION**: Added guardrail: If `JWT_ALGORITHM != HS256` and no JWKS/Key provided, middleware raises 500 at startup/request time.
- **TEST**: Verified via code inspection and unit test logic.

## CHECK D: Require Role Wiring
- **STATUS**: BUG (Confirmed)
- **EVIDENCE**: `require_role` internal dependency did not use `Depends(get_auth_context)`, causing 422 errors.
- **ACTION**: Fixed dependency injection signature.
- **TEST**: `test_middleware.py::test_require_role_dependency` now passes (200 for Admin, 403 for User).

## CHECK E: Tenant Injection
- **STATUS**: VERIFIED (Not a bug after previous phases)
- **EVIDENCE**: APIs read `tenant_id` solely from `AuthContext`.
- **ACTION**: Confirmed removal of `tenant_id` from input models in Ingestion/Query services.
- **TEST**: Integration tests in CI verify isolation.

## CHECK F: CI Evidence
- **STATUS**: DONE
- **ACTION**: Updated `v5-ci.yml` to run auth unit tests and perform a cross-tenant isolation smoke test using generated JWTs.
- **TEST**: CI pipeline execution.
