# TheHive v4 to v5 Feature Mapping & Migration Guide

This document provides a detailed comparison between TheHive v4 (Legacy Monolith) and TheHive v5 (Microservices Architecture). It outlines the mapping of features, data models, and API endpoints.

## 1. Architectural Shift

| Feature | TheHive v4 (Legacy) | TheHive v5 (Core Platform) |
| :--- | :--- | :--- |
| **Architecture** | Monolithic (Scala / Play Framework) | Microservices (Python / FastAPI / Go) |
| **Communication** | In-process calls, Akka Actors | Event-Driven (Kafka/Redpanda), HTTP REST APIs |
| **Primary Datastore** | Cassandra / JanusGraph + ElasticSearch | PostgreSQL (Relational) + OpenSearch (Search/Indexing) |
| **Ingestion Model** | Synchronous (Blocking HTTP) | Asynchronous (Event Sourced, "Fire & Forget") |
| **Indexing** | Real-time (ElasticSearch) | Near Real-time (OpenSearch via Consumer) |
| **Frontend** | AngularJS (1.x) | React / Modern SPA (Planned) / Read-Only Routing for v5 |

## 2. Feature Comparison Matrix

### Alert Management

| Feature | v4 Implementation | v5 Implementation | Status |
| :--- | :--- | :--- | :--- |
| **Create Alert** | `POST /api/alert` (Synchronous) | `POST /ingest` (Async, returns `event_id`) | ✅ Implemented |
| **Deduplication** | Configurable logic in Monolith | `dedup-correlation-service` (Redis-based fingerprinting) | ✅ Implemented |
| **Update Alert** | Supported (Mark as Read, etc.) | Event-driven updates | 🚧 In Progress |
| **List Alerts** | `GET /api/alert` (ElasticSearch) | OpenSearch Query (via Query API) | ✅ Implemented |

### Case Management

| Feature | v4 Implementation | v5 Implementation | Status |
| :--- | :--- | :--- | :--- |
| **Create Case** | `POST /api/case` | Event-driven (Promote Alert) or Direct API | ✅ Implemented |
| **Update Case** | Full CRUD (Metrics, Custom Fields) | `PATCH /cases/{id}` (Title, Desc, Severity, Assignee, Status) | ✅ Basic |
| **Tasks** | `POST /api/case/{id}/task` | `POST /cases/{id}/tasks` | ✅ Implemented |
| **Notes** | `POST /api/case/{id}/log` | `POST /cases/{id}/notes` | ✅ Implemented |
| **Observables** | Full Support (IOCs) | Not yet fully migrated | ❌ Planned |
| **Timeline** | Computed from Audit Log | `GET /cases/{id}/timeline` (Aggregated Tasks/Notes/Links) | ✅ Implemented |

## 3. Data Model Mapping

### Case Object

| Field | v4 Field Name | v5 Field Name | Type/Notes |
| :--- | :--- | :--- | :--- |
| ID | `id` / `_id` | `case_id` | UUID (v5) vs String (v4) |
| Tenant | `organisation` | `tenant_id` | Mandatory Partition Key in v5 |
| Title | `title` | `title` | String |
| Description | `description` | `description` | String (Markdown) |
| Severity | `severity` (1-4) | `severity` (1-4) | Integer |
| Status | `status` | `status` | Enum (OPEN, CLOSED) |
| Owner | `owner` | `assigned_to` | User ID |
| Created By | `createdBy` | `created_by` | User ID |
| Created At | `createdAt` | `created_at` | Timestamp (ms) |
| Updated At | `updatedAt` | `updated_at` | Timestamp (ms) |

### Alert Object

| Field | v4 Field Name | v5 Field Name | Type/Notes |
| :--- | :--- | :--- | :--- |
| Source | `source` | `source` | String |
| Type | `type` | `type` | String |
| SourceRef | `sourceRef` | `sourceRef` | String (Unique per source) |
| Title | `title` | `title` | String |
| Artifacts | `artifacts` | `artifacts` | List of Objects (JSON) |

## 4. API Endpoint Evolution

The v5 API adopts a more standard RESTful approach compared to the v4 API.

### Ingestion

*   **v4**: `POST /api/alert`
    *   Payload: JSON
    *   Response: The created Alert object (JSON).
*   **v5**: `POST /ingest`
    *   Payload: JSON (Schema validated)
    *   Response: `202 Accepted` with `{"event_id": "uuid", "status": "accepted"}`.
    *   *Note*: The client must rely on webhooks or polling to confirm final persistence if strict guarantees are needed, though the `202` implies durability in Kafka.

### Case Operations

*   **v4**: `GET /api/case/{id}`
    *   Returns generic JSON object.
*   **v5**: `GET /cases/{case_id}`
    *   Returns strict schema: `{"case_id": "...", "title": "...", "timeline": [...]}`.

*   **v4**: `PATCH /api/case/{id}`
    *   Complex merge patch logic.
*   **v5**: `PATCH /cases/{case_id}`
    *   Explicit field updates.

## 5. Synchronization & Bridge (Transition Period)

During the migration phase (Strangler Fig pattern), the system operates in a hybrid mode.

### v4 to v5 Sync (Forward)
*   **Mechanism**: Transactional Outbox Pattern.
*   **Source**: `v4_outbox` table in legacy DB.
*   **Destination**: v5 Kafka Topics -> v5 Database/OpenSearch.
*   **Coverage**: Cases, Alerts (Creation & Updates).

### v5 to v4 Writeback (Backward)
*   **Mechanism**: Transactional Inbox Pattern.
*   **Source**: v5 Kafka Topics -> `bridge.v5.writeback.v1`.
*   **Destination**: `v4_inbox` table -> v4 Legacy Tables.
*   **Constraint**: Writeback prevents loops by checking `meta.origin != 'v4'`.
*   **Coverage**: Case Status Updates, Task Creation, Note Addition.
