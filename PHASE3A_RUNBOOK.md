# Phase 3A Runbook

## Service: Alert Ingestion Service

### Overview
Stateless FastAPI service receiving alerts via HTTP and publishing to Redpanda.

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

#### Rollback
- v5 services are additive. Stop the container to stop v5 ingestion.
- v4-LTS is unaffected by v5 failures (fail-open design).
