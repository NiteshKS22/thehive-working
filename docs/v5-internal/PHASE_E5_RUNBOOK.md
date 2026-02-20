# Phase E5 Runbook: Production Hardening

## OIDC / JWKS (Auth)
- **Production Config**: Set `OIDC_ISSUER`, `JWKS_URL`, `JWT_ALGORITHM=RS256`.
- **Rotation**: Keys are cached for 1h. New keys fetched on `kid` miss.
- **Failures**: If JWKS unavailable, auth returns 401/500 (Fail-Closed).

## Secrets Management
- **Loader**: Checks `/run/secrets/{name}` first, then `ENV[{name}]`.
- **Log Redaction**: Secrets are masked in logs.
- **Required Secrets**: `JWT_SECRET` (Dev), `POSTGRES_PASSWORD`, etc.

## API Rate Limits
- **Strategy**: Token bucket per tenant per minute.
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`.
- **Response**: 429 Too Many Requests.

## Contract Governance
- **Gate**: CI checks `EVENT_MODEL.md` vs code.
- **Policy**: Required fields must not be removed.
