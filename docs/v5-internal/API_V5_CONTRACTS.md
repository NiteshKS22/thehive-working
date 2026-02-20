# API v5 Contracts

## Standards
- **Protocol**: REST for public/external, gRPC for internal service-to-service.
- **Versioning**: URI versioning (e.g., `/v5/alerts`).
- **Error Schema**: RFC 7807 Problem Details.

## Idempotency
- **Header**: `Idempotency-Key` required for all state-changing operations.
- **Dedup**: Alerts deduped by sourceRef + type + time window.

## Pagination
- **Cursor-based**: For infinite scroll and high-performance iteration.

## Security
- **AuthN**: OIDC/OAuth2 tokens.
- **AuthZ**: Policy-based (OPA or internal engine).
- **mTLS**: Required for all internal service communication.

## Backward Compatibility with v4-LTS
- v5 APIs may wrap or proxy v4 APIs during transition.
- No changes to existing v4 endpoints.

## Correlation & Groups (Phase 3D)

### List Groups
`GET /groups?tenant_id=...&status=OPEN&q=...`
- **Response**: List of groups matching criteria.
- **Fields**: `group_id`, `status`, `alert_count`, `max_severity`, `rule_name`, `first_seen`, `last_seen`.

### Get Group Details
`GET /groups/{group_id}?tenant_id=...`
- **Response**: Full group details including `correlation_key` and `confidence`.

### Get Group Timeline
`GET /groups/{group_id}/alerts?tenant_id=...`
- **Response**: List of alerts linked to this group, ordered by time.
- **Fields**: Alert details + `link_reason`, `linked_at`.

## Rule Governance (Phase 3F)

### List Rules
`GET /rules`
- **Response**: List of all configured correlation rules.

### Simulate Rule
`POST /rules/simulate?tenant_id=...`
- **Payload**: JSON alert object.
- **Response**: List of hypothetical groups that would be created.

## Authentication (Phase E1)

All v5 APIs require `Authorization: Bearer <JWT>`.
- **Claims Required**: `sub`, `tenant_id`, `roles`, `exp`, `iss`.
- **Tenant Scope**: APIs default to the `tenant_id` in the token. Query parameters for tenant overrides are deprecated/removed.

## Case Management API (Phase E3)

### Create Case
- **POST** `/cases`
- **Permission**: `case:write`
- **Input**: `{ title, description, severity, assigned_to }`
- **Output**: `{ case_id, status: "created" }`

### Update Case
- **PATCH** `/cases/{case_id}`
- **Permission**: `case:write`
- **Input**: `{ title, status, ... }`

### Get Case
- **GET** `/cases/{case_id}`
- **Permission**: `case:read`
- **Output**: Case details.

### List Cases
- **GET** `/cases`
- **Permission**: `case:read`
- **Params**: `status`, `severity`, `limit`, `offset`

### Link Alert
- **POST** `/cases/{case_id}/alerts`
- **Permission**: `case:write`
- **Input**: `{ original_event_id, link_reason }`
