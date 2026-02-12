# Phase E1 Runbook: Identity & Zero-Trust

## Authentication Model
v5-Internal uses JWT-based authentication (Bearer Token).
- **Tenant Isolation**: `tenant_id` is extracted from the JWT payload. Query parameters for tenant overrides are FORBIDDEN.
- **Identity Provider**: Currently set to `dev-secret-do-not-use-in-prod` (HS256). Production will use OIDC (RS256).

## Role-Based Access Control (RBAC)
Roles are defined in the Postgres `roles` table.
- **SOC_ANALYST**: Can read alerts/groups.
- **RULE_ADMIN**: Can manage correlation rules.
- **SYSTEM_ADMIN**: Full access.

## Operations

### Testing Auth
Use the helper script to generate a token:
```bash
python3 .github/scripts/generate_test_token.py <username> <tenant-id> <roles>
export TOKEN=...
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/alerts
```

### Dev Mode
To bypass auth locally, set `DEV_MODE=true` in `middleware.py` config (not recommended for integration tests).

### Troubleshooting
#### "401 Unauthorized"
- Token expired or invalid signature.
- Check `JWT_SECRET` environment variable match.

#### "403 Forbidden"
- Missing `tenant_id` in token.
- User lacks required role.
