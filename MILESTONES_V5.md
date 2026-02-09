# Phase 3 Milestones: v5-Internal Implementation

## Epics

### 1. Ingestion Engine Implementation
- **Goal**: Build production-ready Ingestion Service using FastAPI/Go.
- **Criteria**: High-throughput ingestion, validation against canonical schema, push to Kafka/EventBus.

### 2. Alert Deduplication & Correlation
- **Goal**: Implement dedup logic in the stream processor.
- **Criteria**: Configurable window-based dedup; correlation engine matching IoCs.

### 3. Async Enrichment Workers
- **Goal**: Decouple Cortex/Ollama calls from the critical path.
- **Criteria**: Worker pool consuming enrichment events; result write-back to v5 store.

### 4. Storage & Event Store
- **Goal**: Provision and connect the v5 persistent store (e.g., PostgreSQL + S3 or specialized Event Store).
- **Criteria**: Append-only log operational; immutable audit trail active.

### 5. Responders & SOAR Hooks
- **Goal**: Event-driven triggers for external SOAR systems.
- **Criteria**: Webhook delivery on `AlertCreated`/`CaseCreated` events.

### 6. Reporting & Analytics Service
- **Goal**: Read-optimized view for dashboards.
- **Criteria**: Analytics API endpoints serving aggregated metrics.

### 7. Dual-Write Integration
- **Goal**: Wire v4-LTS inputs to v5 Ingestion.
- **Criteria**: Traffic mirroring active; comparison dashboard showing v4 vs v5 latency/volume.

### 8. Production Cutover (Ingestion)
- **Goal**: Switch primary ingestion path to v5.
- **Criteria**: KPIs met; rollback toggle tested; v4 becomes subscriber to v5 events.
