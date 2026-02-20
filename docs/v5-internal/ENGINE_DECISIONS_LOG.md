# Engine Decisions Log (ADR)

**Status**: Baseline (Phase 0 - E1)
**Last Updated**: 2026-02-11

This document tracks significant architectural decisions for the v5-Internal engine.

## ADR-001: Strangler Fig Pattern for Modernization
- **Context**: The legacy TheHive 4 monolith is difficult to maintain and scale.
- **Decision**: Build v5-Internal as a parallel "Headless Engine" handling high-volume ingestion and search, while treating v4-LTS as immutable for UI/Case Management.
- **Consequences**: Requires careful synchronization logic later. Traffic flows one-way (Ingest -> v5) initially.
- **Status**: Active (Phase 0).

## ADR-002: Redpanda as Event Spine
- **Context**: High throughput event streaming is required. Kafka is the standard but complex to operate.
- **Decision**: Use Redpanda (Kafka API compatible) for its single-binary architecture and high performance.
- **Consequences**: Simplifies ops (no Zookeeper). Compatible with standard Kafka clients.
- **Status**: Active (Phase 3A).

## ADR-003: FastAPI for Services
- **Context**: Python is preferred for speed of development and ecosystem.
- **Decision**: Use FastAPI + Pydantic + Uvicorn for Ingestion and Query services.
- **Rationale**: Async IO performance, strict schema validation, auto-generated OpenAPI docs.
- **Status**: Active (Phase 3A).

## ADR-004: Redis with AOF for Deduplication
- **Context**: Alerts must be deduplicated efficiently to prevent noise.
- **Decision**: Use Redis with Append-Only File (AOF) persistence. Use `SET NX` with TTL for idempotent fingerprinting.
- **Rationale**: Low latency, atomic operations. AOF ensures data survives restarts.
- **Status**: Active (Phase 3B).

## ADR-005: Manual Offset Commits & At-Least-Once Delivery
- **Context**: Data loss is unacceptable. Auto-commit can lose messages if processing fails after commit.
- **Decision**: Disable `enable_auto_commit`. Consumers manually commit offsets ONLY after successful DB write + Producer flush OR successful DLQ publish.
- **Consequences**: Potential duplicates during replays (consumers must be idempotent). Guarantees at-least-once.
- **Evidence**: `v5-core/correlation-service/app/main.py`.
- **Status**: Active (Phase 3B/3D).

## ADR-006: Tenant ID in Top-Level Event Envelope
- **Context**: Multi-tenancy is a strict requirement.
- **Decision**: `tenant_id` is a mandatory top-level field in every Kafka message schema (Ingest -> Group).
- **Rationale**: Allows consumers to route/filter without parsing the full payload. Enforced at Ingestion.
- **Status**: Active (Phase 3A).

## ADR-007: OpenSearch for Read Model
- **Context**: Analysts need fast, flexible search over alerts and groups.
- **Decision**: Use OpenSearch (Elasticsearch fork) as the dedicated Read Model projection.
- **Rationale**: License compatibility, strong search capabilities.
- **Consequences**: Eventual consistency between Source of Truth (Postgres) and Search (OpenSearch).
- **Status**: Active (Phase 3C).

## ADR-008: Deterministic IDs for Idempotency
- **Context**: Replays (At-Least-Once) can duplicate data.
- **Decision**:
    -   Alerts: `_id = original_event_id`.
    -   Groups: `_id = hash(tenant_id:rule:key:window)`.
- **Rationale**: Re-indexing the same event overwrites the document (Idempotent Upsert) rather than creating duplicates.
- **Correction**: Phase 3C.1 corrected `_id` from fingerprint to event_id to prevent data loss on hash collision.
- **Status**: Active (Phase 3C.1).

## ADR-009: Postgres for Correlation State
- **Context**: Correlation involves complex relationships (Links) and state (Groups) requiring ACID guarantees.
- **Decision**: Use PostgreSQL for the Correlation Service state store.
- **Rationale**: Relational integrity, transaction support for atomic Group+Link creation.
- **Status**: Active (Phase 3D).

## ADR-010: Kafka Partition Keying by Group ID
- **Context**: `GroupCreated` and `GroupUpdated` events must be processed in order by the Indexer.
- **Decision**: Producer MUST use `key=group_id` for correlation output topics.
- **Rationale**: Ensures all events for a specific group land on the same Kafka partition, guaranteeing sequential processing.
- **Status**: Active (Phase 3D Audit).

## ADR-011: Global Rules with Tenant Execution
- **Context**: Rules need to be managed centrally but applied per tenant.
- **Decision**: `correlation_rules` table has no `tenant_id`. Rules are global system templates.
- **Rationale**: Simplifies rule management. Tenant isolation is enforced at runtime by applying rules only to alerts within the same tenant scope.
- **Status**: Active (Phase 3E/3F).

## ADR-012: Dynamic Rule Reloading
- **Context**: Restarting services to apply rule changes is disruptive.
- **Decision**: Correlation Service polls Postgres for rule changes (background thread).
- **Rationale**: Allows runtime tuning without downtime.
- **Status**: Active (Phase 3F).

## ADR-013: Read-Only Simulation
- **Context**: Analysts need to test rules safely.
- **Decision**: `POST /rules/simulate` runs logic in-memory and returns JSON results. It performs NO writes to DB/Kafka.
- **Status**: Active (Phase 3F).

## ADR-014: Defense-in-Depth Tenant Filtering (Query API)
- **Context**: A compromised or corrupted OpenSearch index could return cross-tenant data.
- **Decision**: Query API validates `doc['tenant_id'] == auth.tenant_id` on every result fetched from OpenSearch, even if the query included a filter.
- **Status**: Active (Phase 3E/3F Audit).

## ADR-015: JWT Authentication & Claims
- **Context**: Zero-Trust security model.
- **Decision**: Use JWT Bearer tokens. Require `sub`, `tenant_id`, `roles`.
- **Rationale**: Stateless, standard, carries isolation context securely.
- **Status**: Active (Phase E1).

## ADR-016: Strict DEV_MODE
- **Context**: Developers need local ease-of-use, but this opens security holes if deployed.
- **Decision**: `DEV_MODE=true` enables header overrides ONLY if `ALLOW_DEV_OVERRIDES=true` is also set. Default is safe.
- **Status**: Active (Phase E1).

## ADR-017: RS256 Startup Guardrail
- **Context**: Misconfigured Auth (e.g. RS256 without keys) causes runtime 500s or insecurity.
- **Decision**: Middleware checks config at module import/startup. Calls `sys.exit()` (or raises `RuntimeError`) if unsafe configuration detected. Fail Fast.
- **Status**: Active (Phase E1).

## ADR-018: CI Network Isolation
- **Context**: `--network host` in CI is fragile and doesn't mirror prod.
- **Decision**: Use `docker-compose` created network (`event-spine_default`). Services communicate via internal DNS.
- **Status**: Active (Phase 3D Audit).

## ADR-019: Additive Correlation
- **Context**: Correlation must not hide data.
- **Decision**: Correlation adds metadata (Groups, Links). It NEVER suppresses or modifies the original Alert. Raw alerts remain searchable.
- **Status**: Active (Phase 3D).

## ADR-020: Fail-Open Architecture
- **Context**: Correlation service downtime shouldn't stop ingestion.
- **Decision**: Ingestion/Dedup/Indexing are decoupled from Correlation. If Correlation Service dies, alerts are still ingested and indexed (just not grouped).
- **Status**: Active (Phase 3D).

## ADR-021: Granular RBAC Permissions
- **Context**: Role-based access control (RBAC) was too coarse (Admin/Analyst/Ingest).
- **Decision**: Implement fine-grained permissions (e.g., `alert:read`, `case:update`) mapped from roles. Enforce permissions in middleware.
- **Rationale**: Allows flexible policy definition and strict least-privilege enforcement.
- **Status**: Active (Phase E2).

## ADR-022: Postgres for Case Domain Storage
- **Context**: Case management requires transactional consistency (ACID) for tasks, notes, and state.
- **Decision**: Use PostgreSQL (existing cluster) with new tenant-isolated tables.
- **Rationale**: Relations (Tasks <-> Cases) are strictly hierarchical. No need for NoSQL or Search engine for primary state.
- **Status**: Active (Phase E3).

## ADR-023: CQRS-Lite for Case APIs
- **Context**: We need to separate Write logic (Case Service) from Read logic (Query Service) to maintain architecture symmetry.
- **Decision**: `case-service` handles Writes. `query-api-service` handles Reads (proxying to Postgres for E3).
- **Rationale**: Keeps  focused on business rules/side-effects.  remains the single pane of glass.
- **Status**: Active (Phase E3).

## ADR-024: Standardized Commit & DLQ Strategy
- **Context**: Consumers had inconsistent commit behavior (some auto, some manual).
- **Decision**: All consumers MUST disable auto-commit. Offsets are committed ONLY after processing success OR successful DLQ publish. If DLQ fails, offsets are NOT committed (fail-safe).
- **Rationale**: Prevents data loss (At-Least-Once). Ensures bad data is quarantined without blocking the pipeline.
- **Status**: Active (Phase E4.1).

## ADR-025: Backpressure & Retry Policy
- **Context**: Consumers were at risk of OOM on large bursts and infinite loops on transient errors.
- **Decision**: 
    1. Limit `max_poll_records` to 100.
    2. Implement 3x exponential backoff retry for transient errors.
    3. Implement explicit sleep backpressure if processing exceeds thresholds.
- **Status**: Active (Phase E4.2).

## ADR-026: Observability Standards
- **Context**: Services lacked visibility into internal state (consumer lag, errors).
- **Decision**: 
    1. All HTTP services expose Prometheus metrics on `/metrics`.
    2. All Workers expose Prometheus metrics on dedicated internal ports (900X).
    3. Standardize on `/healthz` (always 200) and `/readyz` (dependency check).
- **Rationale**: Enables K8s probes and Prometheus scraping without vendor lock-in.
- **Status**: Active (Phase E4.3).

## ADR-027: Secrets Loading Strategy
- **Context**: Hardcoded secrets and simple env vars are insufficient for secure orchestration.
- **Decision**: Use a helper that prefers `/run/secrets/<name>` over `ENV`. Fail startup if required secrets are missing.
- **Status**: Active (Phase E5).

## ADR-028: RS256/JWKS Enforcement
- **Context**: HS256 shared secrets scale poorly and are less secure.
- **Decision**: Enforce RS256 with OIDC discovery (JWKS) in non-dev environments. Cache keys in memory.
- **Status**: Active (Phase E5).

## ADR-029: Tenant-Isolated Rate Limiting
- **Context**: No protection against noisy tenants.
- **Decision**: Implement sliding window limit per tenant (via AuthContext). Return 429.
- **Status**: Active (Phase E5).

## ADR-030: Strangler Bridge Architecture (Phase B1)

### Status
Accepted

### Context
To migrate from v4-LTS (Monolith) to v5-Internal (Microservices) without a "Big Bang" rewrite, we need a mechanism to synchronize state bi-directionally. v4 must remain the system of record for the UI during the transition.

### Decision
We will implement a **Strangler Fig Pattern** with an **Event Outbox** on the v4 side and a **Sync Adapter** on the v5 side.

1.  **v4 Outbox:** v4 will write domain events to a transactional outbox table (or use a CDC-like trigger approach if feasible without intrusive code changes). A publisher process will read this outbox and publish to Redpanda.
2.  **v5 Sync Adapter:** A new service, `v4-sync-service`, will consume these events and update the v5 Case/Alert stores.
3.  **Conflict Resolution:** `GREATEST(updated_at)` logic will be used. In Phase B1, v4 is authoritative.
4.  **Reversibility:** The bridge can be disabled via feature flag.

### Consequences
-   **Pros:** Enables incremental migration. Decouples v4 and v5 runtimes. Allows v5 to be "read-only" regarding state origin initially.
-   **Cons:** Introduces eventual consistency latency. Requires careful handling of drift and conflicts. Adds operational complexity (monitoring the bridge).

### Compliance
-   **Tenant Isolation:** Enforced by the trusted publisher.
-   **Zero Trust:** v5 services treat bridge events as external inputs requiring validation.

## ADR-031: v4 Outbox Pattern for Bridge Publishing (Phase B1.1)

### Status
Accepted

### Context
We need to emit domain events from the legacy v4 system to the v5 event spine without modifying v4's core business logic or risking dual-write inconsistencies.

### Decision
We will use the **Transactional Outbox Pattern**.
1.  **Additive Schema:** A `v4_outbox` table is added to the v4 database.
2.  **Publisher Service:** A standalone `v4-outbox-publisher` polls this table (using `SKIP LOCKED`) and publishes to Redpanda.
3.  **Idempotency:** Each outbox record has a deterministic UUID. Kafka keys are stable (`tenant:type:id`).
4.  **Reversibility:** The publisher can be stopped instantly. The table remains but processing halts.

### Consequences
-   **Pros:** Atomic with v4 state changes (if v4 writes to outbox in same tx). Decoupled from v4 runtime performance (async).
-   **Cons:** Polling introduces slight latency. Requires new service to manage.

### Compliance
-   **Tenant Isolation:** `tenant_id` is mandatory in the outbox schema and must be populated by the v4 application from authoritative context.
-   **Security:** Publisher uses SSL/TLS for Kafka.
