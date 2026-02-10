# Phase 3A Runbook: Alert Ingestion Service

## Service: Alert Ingestion Service

### Overview
Stateless FastAPI service receiving alerts via HTTP and publishing to Redpanda.

### Hardening (Phase 3A/3B Update)
- **Validation**: Strict Pydantic models (v2/v1 compat) used for request parsing.
- **Tenant ID**: The `Alert` model now includes `tenant_id` (defaults to `default`). This is required for downstream dedup isolation.
- **Idempotency**: `Idempotency-Key` header is propagated to event payload.

### Operations

#### Start/Stop
Managed via Docker Compose or K8s (future).
```bash
cd v5-core/event-spine && docker-compose up -d
docker run ... thehive-ingestion:latest
```

#### Logs
- **Format**: JSON structured logging.
- **Key Fields**: `trace_id`, `event_id`, `level`.
- **Access**: stdout/stderr.

#### Monitoring
- `GET /health`: Liveness check. Returns 200 OK.
- `GET /metrics` (planned): Prometheus metrics.

### Troubleshooting

#### "Kafka Connection Failed"
- Check Redpanda connectivity: `rpk cluster info` inside redpanda container.
- Verify `KAFKA_BOOTSTRAP_SERVERS` env var.

#### "Ingestion Failed" (500)
- Check logs for stack trace.
- Ensure topic `alerts.ingest.v1` exists.

#### "Missing Tenant ID" (Downstream Error)
- Ensure the JSON payload includes `tenant_id` or verify the service defaults it correctly.
- Check dedup service logs or DLQ topic `alerts.ingest.dlq.v1`.

#### Rollback
- v5 services are additive. Stop the container to stop v5 ingestion.
- v4-LTS is unaffected by v5 failures (fail-open design).
