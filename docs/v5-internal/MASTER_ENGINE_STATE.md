# 1. Executive Overview

**v5-Internal** is a "Headless SOC Platform" architecture designed to decouple high-value ingestion, correlation, and search capabilities from the legacy TheHive 4 monolith. It follows the **Strangler Fig Pattern**, allowing v5 services to run alongside v4-LTS without disrupting existing operations.

### Mission
To provide a production-grade, event-driven engine that handles data ingestion, deduplication, correlation, and search with strict multi-tenant isolation and zero-trust security.

### Relationship to v4-LTS
- **v4-LTS**: Maintains the legacy UI/UX and Case Management logic.
- **v5-Internal**: Handles high-volume event processing. Data flows ONE WAY (Ingest -> v5). Future phases may sync v5 data back to v4 or replace v4 modules entirely.

### Non-Negotiable Guardrails
1.  **No v4 Changes**: The legacy codebase is treated as immutable.
2.  **Tenant Isolation**: Enforced at every layer (API, Event, DB, Search).
3.  **Fail-Open**: v5 failures must not crash v4 or stop ingestion.
4.  **Zero-Trust**: All services require explicit authentication (JWT).

### Current Status
**Maturity**: Beta / Pre-Production Hardening.
- Core pipeline (Ingest -> Dedup -> Index) is functional.
- Correlation engine is live with governance.
- Identity layer (AuthN/AuthZ) is enforced.
- **Missing**: Full Case Management, SOAR, mTLS, Production OIDC wiring.

---

# 2. Phase-by-Phase Architecture History

## Phase 0 — Foundation

### Objective
Establish a reproducible, secure build and CI/CD environment.

### Why This Was Needed
Legacy builds were flaky and insecure. We needed a clean slate for v5 services.

### Components Introduced
- `.github/workflows/v5-ci.yml`
- `tests/smoke_api/`
- `tests/smoke_ui/` (Playwright stub)

### Architectural Decisions
- **GitHub Actions**: Standardized CI runner.
- **Docker Compose**: Local stack replication for integration tests.

### CI/CD Changes
- Added `v5-ci.yml` running independently of legacy pipelines.

---

## Phase 3A — Ingestion Service

### Objective
Create a high-throughput, stateless entry point for alerts.

### Why This Was Needed
Legacy ingestion was coupled to the monolith and slow.

### Components Introduced
- `alert-ingestion-service` (FastAPI)
- `redpanda` (Kafka-compatible event bus)

### Architectural Decisions
- **Redpanda**: Chosen for Kafka compatibility, single-binary simplicity, and high throughput.
- **FastAPI**: Async performance and strict Pydantic validation.
- **Trace ID**: `X-Trace-Id` propagated from ingress to all downstream events.

### Data Contracts
- **Input**: JSON Alert Payload.
- **Output**: `alerts.ingest.v1` (Event: `AlertCreated`).

---

## Phase 3B — Deduplication Service

### Objective
Prevent duplicate alerts from flooding the system while ensuring idempotency.

### Why This Was Needed
Alert sources often retry or resend the same signal.

### Components Introduced
- `dedup-correlation-service` (Python Worker)
- `redis` (State Store)

### Architectural Decisions
- **Redis AOF**: Persistence enabled to survive restarts.
- **Manual Offset Commit**: Consumer commits ONLY after successful processing/publish to ensure At-Least-Once delivery.
- **DLQ**: Malformed events sent to `alerts.ingest.dlq.v1`.

### Data Contracts
- **Input**: `alerts.ingest.v1`
- **Output**: `alerts.accepted.v1` / `alerts.duplicate.v1`

---

## Phase 3C — OpenSearch Read Model

### Objective
Provide fast, tenant-isolated search for alerts.

### Why This Was Needed
Legacy Elastic/Cassandra queries were slow and hard to scale.

### Components Introduced
- `opensearch-indexer-service` (Python Worker)
- `query-api-service` (FastAPI)
- `opensearch` (Search Engine)

### Architectural Decisions
- **OpenSearch**: Fork of Elasticsearch, compatible with license needs.
- **Deterministic IDs**: Doc `_id` derived from `original_event_id` (or fingerprint) to ensure idempotent re-indexing.
- **Tenant Filter**: Query API enforces `tenant_id` filter on EVERY search.

### Phase 3C.1 Fix
- **Correction**: Changed Indexer `_id` to use `original_event_id` instead of  to prevent overwriting distinct alerts that look similar.

---

## Phase 3D — Correlation Engine

### Objective
Group related alerts into Incidents based on logic rules.

### Why This Was Needed
Analysts were overwhelmed by raw alert volume.

### Components Introduced
- `correlation-service` (Python Worker)
- `group-indexer-service` (Python Worker)
- `postgres` (Relational State Store)

### Architectural Decisions
- **Postgres**: Selected for ACID compliance on Group/Link state (critical data).
- **Partition Key**: Producer uses `key=group_id` to ensure strict ordering of Group updates.
- **Greatest Timestamp**: DB updates use `GREATEST(updated_at, ...)` to handle out-of-order events safeley.

### Data Contracts
- **Events**: `correlation.group.created.v1`, `correlation.group.updated.v1`, `correlation.alert.linked.v1`.

---

## Phase 3E/3F — Analyst UI & Governance

### Objective
Make correlation visible and controllable.

### Why This Was Needed
"Black box" grouping confuses analysts. Rules need runtime tuning.

### Components Introduced
- **Rule Registry**: `correlation_rules` table in Postgres.
- **Simulation API**: `POST /rules/simulate` (Stateless dry-run).
- **Audit**: `correlation.audit.v1` events.

### Architectural Decisions
- **Global Rules**: Rules are defined globally (system templates) but applied within tenant boundaries.
- **Dynamic Reload**: Correlation service polls DB for rule changes.

---

## Phase E1 — Identity & Zero-Trust

### Objective
Secure the engine with production-grade AuthN/AuthZ.

### Why This Was Needed
Previous phases relied on query parameters for tenancy (insecure).

### Components Introduced
- `common/auth/middleware.py` (Shared Library)
- `roles`, `permissions` tables in Postgres.

### Architectural Decisions
- **JWT**: Bearer tokens required.
- **Claims**: `tenant_id` MUST be in token.
- **RS256 Guardrail**: Service fails startup if configured for RS256 without keys.
- **Safe DEV_MODE**: Header overrides ignored unless `ALLOW_DEV_OVERRIDES=true`.

---

# 3. Current Engine Topology (Authoritative)

## Runtime Components
1.  **alert-ingestion-service**: Public ingress (AuthZ: JWT).
2.  **dedup-correlation-service**: Worker (Redis).
3.  **correlation-service**: Worker (Postgres).
4.  **opensearch-indexer-service**: Worker (OpenSearch).
5.  **group-indexer-service**: Worker (OpenSearch).
6.  **query-api-service**: Public search API (AuthZ: JWT).

## Infrastructure
- **Redpanda**: Ports 9092 (Internal), 8081 (Schema).
- **Redis**: Port 6379 (AOF Persistence).
- **Postgres**: Port 5432 (Tables: `correlation_groups`, `rules`, `roles`).
- **OpenSearch**: Ports 9200/9600.

## Event Flow
1.  **Ingest** -> `alerts.ingest.v1`
2.  **Dedup** -> `alerts.accepted.v1` OR `alerts.duplicate.v1`
3.  **Correlate** ->
    -   `correlation.group.created.v1`
    -   `correlation.group.updated.v1`
    -   `correlation.alert.linked.v1`
    -   `correlation.audit.v1`
4.  **Indexing**: Consumers read above topics -> OpenSearch Indices.

---

# 4. Multi-Tenant Isolation Model

- **Ingestion**: Removes `tenant_id` from user input. Injects it from validated JWT.
- **Processing**: All Kafka messages carry `tenant_id` at top level.
- **Storage**:
    -   Postgres PKs: `(tenant_id, id)`.
    -   OpenSearch: Documents contain `tenant_id`.
- **Access**:
    -   Query API extracts `tenant_id` from JWT.
    -   Appends `filter: { term: { tenant_id: ... } }` to ALL OpenSearch queries.
    -   Validates `tenant_id` on returned documents (Defense-in-Depth).

---

# 5. Identity & Auth (Phase E1)

- **Standard**: OIDC / JWT Bearer Tokens.
- **Algorithm**: RS256 (Prod), HS256 (Dev).
- **Guardrails**:
    -   Fail-fast on startup if config is insecure.
    -   Normalize roles (string vs list).
    -   Require `sub` and `tenant_id` claims.
- **RBAC**: Code uses `@require_role(["ROLE"])` which validates against `AuthContext`.

---

# 6. Reliability & Safety Model

- **At-Least-Once Delivery**:
    -   Manual offset commits ONLY after successful processing.
    -   If DB/Logic fails -> DLQ attempt.
    -   If DLQ fails -> No Commit (Replay occurs).
- **Idempotency**:
    -   Redis SETNX for Dedup.
    -   Postgres `ON CONFLICT DO NOTHING/UPDATE`.
    -   Deterministic UUIDs based on content hashes.
- **Data Integrity**:
    -   Audit logs for correlation decisions.
    -   Timestamp guards (`GREATEST` logic) for out-of-order updates.

---

# 7. What Is NOT Yet Implemented (Critical)

- **Case Management**: No case/task/SLA logic.
- **UI**: No frontend (Headless only).
- **mTLS**: Service-to-service calls are internal network only (unencrypted inside cluster).
- **Secrets Management**: Env vars used directly (Vault integration pending).
- **Production OIDC**: Currently using Dev Secret in CI.

---

# 8. Engine Completeness Assessment

**Status**: **BETA / ENGINEERING PREVIEW**

The engine is functional and secure for backend use cases. It correctly handles multi-tenancy and data flow. Reliability hardening (DLQ, Idempotency) is complete. It is **READY** for:
- Integration testing with real data.
- UI development (Phase 3E/3F UI build).
- Pilot migration of ingestion traffic.

It is **NOT READY** for:
- General Availability (GA) without a frontend.
- High-Compliance environments (needs mTLS/Secrets).

---

# 9. Remaining Engine Roadmap

1.  **Phase E2**: Advanced RBAC (Granular Permissions).
2.  **Phase E3**: Case Management Domain (Backend).
3.  **Phase E4**: Reliability Hardening (Backpressure, Autoscaling).
4.  **Phase E5**: Operational Governance (Metrics, Dashboards).

---

# 10. Cutover Readiness Criteria

Before moving full traffic:
1.  Auth must be wired to corporate OIDC.
2.  Observability dashboards (Grafana) must be live.
3.  Load testing (10k EPS) must pass.
4.  Security Audit (Pen Test) of Query API.

## Phase E3 — Case Management Domain

### Objective
Implement the backend logic for Case Management (Cases, Tasks, Notes, Links) within the v5 engine, decoupled from v4.

### Why This Was Needed
To prepare for UI migration and enable API-first case management.

### Components Introduced
- `case-service` (FastAPI): Handles Case mutations (Create, Update, Link).
- `cases`, `case_tasks`, `case_notes`, `case_alert_links` tables (Postgres).

### Architectural Decisions
- **Postgres as Source of Truth**: Case state requires ACID compliance.
- **CQRS-Lite**: `case-service` handles Writes. `query-api-service` handles Reads (proxying to Postgres for E3).
- **Tenant Isolation**: Enforced via `tenant_id` in PKs and AuthContext.

### Data Contracts
- **Events**: `cases.created.v1`, `cases.updated.v1`, `cases.closed.v1`, etc.
- **Payloads**: See `EVENT_MODEL.md`.

## Phase E4.3 — Observability & Health

### Objective
Provide visibility into the black-box engine components.

### Components Introduced
- **Metrics Middleware**: Auto-instrumentation for HTTP services.
- **Sidecar Metrics**: HTTP servers for Kafka workers.
- **Health/Ready Probes**: Standardized /healthz and /readyz.

### Standards
- **Metrics Path**: `/metrics` (Prometheus format).
- **Health Path**: `/healthz` (Liveness), `/readyz` (Readiness).
- **Ports**: HTTP (8000-8002), Workers (9001-9004).

## Phase E5 — Production Security & Platform

### Objective
Harden the engine for production deployment (GA readiness).

### Components Introduced
- **OIDC/JWKS**: RS256 enforcement, key caching.
- **Secrets Loader**: Secure config management.
- **Rate Limiting**: Token bucket per tenant.
- **Contract Gate**: CI check for schema compliance.

### Security Posture
- **Auth**: Production-grade (Fail-Closed).
- **Secrets**: Redacted in logs, loaded from file/env.
- **DoS Protection**: Active.

### Maturity Status: PRODUCTION-READY (Pending Frontend)
- **v5-Internal** is now feature-complete for backend operations.
- Security (Auth/Secrets/mTLS), Reliability (DLQ/Retry/Backpressure), and Observability (Metrics/Health) are implemented.
- **Next**: Phase E6 (UI Migration & Legacy Sunset).

## Phase B1 - Bridge Layer (Active)
**Status:** In Progress
**Objective:** Bi-directional sync between v4-LTS and v5-Internal.
**Implemented Components:**
-   `docs/v5-internal/BRIDGE_EVENT_MODEL.md`
-   `v5-core/v4-sync-service` (Consumer Adapter)
**Pending:**
-   v4-Side Outbox Publisher (Requires v4 code access/DB trigger).
-   Full end-to-end integration tests.

## Phase B1.1 - v4 Outbox Publisher (Active)
**Status:** In Progress
**Objective:** Enable v4 to publish authoritative events to v5.
**Implemented Components:**
-   `migration/v4_outbox_schema.sql`
-   `v4-bridge/v4-outbox-publisher` (Service)
-   `bridge.v4.*` topics
**Pending:**
-   Integration with actual v4 codebase (trigger/hook implementation).
