# Phase 3B Runbook: Dedup & Correlation Service

## Service: Dedup Worker

### Overview
A Python consumer/producer service that reads `AlertCreated` events, checks fingerprints against Redis, and emits `AlertAccepted` or `AlertDuplicateRejected`.

### Operations

#### Configuration
- `DEDUP_WINDOW_SECONDS`: Time window for deduplication (default: 600s).
- `REDIS_HOST`: Redis connection host.

#### Monitoring
- **Metrics**:
  - `dedup_processed_total`: Count of events processed.
  - `dedup_duplicates_total`: Count of rejected duplicates.
  - `dedup_accepted_total`: Count of accepted alerts.
- **Logs**:
  - Look for `Duplicate rejected: <fingerprint>` or `Alert accepted: <fingerprint>`.

### Troubleshooting

#### "High Dedup Latency"
- Check Redis latency: `redis-cli --latency`.
- Ensure `AOF` rewrite isn't blocking (check Redis logs).

#### "Events Not Processed"
- Verify consumer group status: `rpk group describe dedup-group-v1`.
- Check if worker is crashing/restarting (OOM?).

#### "Redis Memory Full"
- Check eviction policy. It should be `volatile-ttl` or `allkeys-lru`.
- Increase Redis memory limit in `docker-compose.yml` or k8s resources.

#### Rollback
- Stop the dedup container.
- If needed, flush Redis (warning: resets dedup windows).
