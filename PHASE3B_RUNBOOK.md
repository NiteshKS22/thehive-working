# Phase 3B Runbook: Dedup & Correlation Service

## Service: Dedup Worker

### Overview
A Python consumer/producer service that reads `AlertCreated` events, checks fingerprints against Redis, and emits `AlertAccepted` or `AlertDuplicateRejected`.

### Hardening & Production Semantics (Phase 3B Update)
- **Manual Offset Management**: Auto-commit is disabled (). Offsets are committed ONLY after successful processing and producer flush.
- **Dead Letter Queue (DLQ)**: Events missing critical fields (e.g., `tenant_id`) are sent to `alerts.ingest.dlq.v1` instead of crashing the worker.
- **Tenant Isolation**: All dedup keys in Redis are prefixed with `tenant_id` (e.g., `dedup:{tenant_id}:{fingerprint}`).
- **Configurable Reset**: `AUTO_OFFSET_RESET` defaults to `latest` but can be set to `earliest` for replay.

### Operations

#### Configuration
- `DEDUP_WINDOW_SECONDS`: Time window for deduplication (default: 600s).
- `REDIS_HOST`: Redis connection host.
- `AUTO_OFFSET_RESET`: Kafka consumer start position (default: `latest`).

#### Monitoring
- **Metrics**:
  - `dedup_processed_total`: Count of events processed.
  - `dedup_duplicates_total`: Count of rejected duplicates.
  - `dedup_accepted_total`: Count of accepted alerts.
- **Logs**:
  - Look for `Duplicate rejected: <fingerprint>` or `Alert accepted: <fingerprint>`.
  - Look for `Missing tenant_id ... Sending to DLQ` for malformed events.

### Troubleshooting

#### "High Dedup Latency"
- Check Redis latency: `redis-cli --latency`.
- Ensure `AOF` rewrite isn't blocking (check Redis logs).

#### "Events Not Processed"
- Verify consumer group status: `rpk group describe dedup-group-v1`.
- Check if worker is crashing/restarting (OOM?).
- Check DLQ topic: `rpk topic consume alerts.ingest.dlq.v1`.

#### "Redis Memory Full"
- Check eviction policy. It should be `volatile-ttl` or `allkeys-lru`.
- Increase Redis memory limit in `docker-compose.yml` or k8s resources.

#### Rollback
- Stop the dedup container.
- If needed, flush Redis (warning: resets dedup windows).
