# Phase 3D Runbook: Correlation & Grouping

## Service: Correlation Service

### Overview
Stateful worker consuming `alerts.accepted.v1` and grouping them into incidents (Correlation Groups) based on configurable rules.

### Key Features
- **Deterministic Grouping**: Alerts with same `correlation_key` + time window map to same `group_id`.
- **Tenant Isolation**: All keys/groups are scoped by `tenant_id`.
- **Idempotency**: Safe for replay. DB constraints prevent duplicate links.

### Configuration
- `RULES_FILE`: Path to rules definition (default: `rules.yaml`).
- `POSTGRES_...`: Database connection.
- `KAFKA_...`: Redpanda connection.

### Operations
#### Reload Rules
Currently requires service restart.
```bash
docker restart correlation-service
```

#### Check Processing
Tail logs:
```bash
docker logs -f correlation-service
```
Look for "Group Created" or "Group Updated".

#### Inspect Database
Connect to Postgres:
```bash
docker exec -it v5-postgres psql -U hive -d v5_events
SELECT * FROM correlation_groups ORDER BY updated_at DESC LIMIT 5;
```

## Service: Group Indexer

### Overview
Consumes correlation events and updates OpenSearch `groups-v1` index for fast listing.

### Operations
#### Re-index Groups
If OpenSearch data is lost or corrupt, you can replay `correlation.group.*` topics from earliest offset.
```bash
# Reset consumer group offset
rpk group seek group-indexer-v1 --to-earliest
```

## Query API

### Endpoints
- `GET /groups?tenant_id=...`: List groups.
- `GET /groups/{id}?tenant_id=...`: Get group details.
- `GET /groups/{id}/alerts?tenant_id=...`: Get timeline of alerts in group.

### Troubleshooting
#### "Group missing in UI but present in DB"
- Check `group-indexer-service` logs.
- Verify `groups-v1` index exists in OpenSearch.

#### "Alert count mismatch"
- DB is authoritative source. OpenSearch is projection (eventually consistent).
- Check if `correlation.group.updated.v1` events are being produced/consumed.
