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
