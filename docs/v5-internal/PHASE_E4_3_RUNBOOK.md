# Phase E4.3 Runbook: Observability & Health

## Health Checks
- **Liveness**: `GET /healthz` (Always 200)
- **Readiness**: `GET /readyz` (Dependency Checks)

## Metrics
- **Endpoint**: `GET /metrics` (Prometheus format)
- **Standard Labels**: `service`, `env`

## Alerting Thresholds (Guardrails)
- **Consumer Lag**: > 1000 messages (Warning), > 10000 (Critical)
- **DLQ Rate**: > 0 messages/min (Critical)
- **Error Rate**: > 1% (Warning), > 5% (Critical)
- **Latency p95**: > 200ms (Ingest), > 1s (Query)

## Troubleshooting
- **If Readyz Fails**: Check logs for specific dependency failure (Postgres, Kafka, OpenSearch).
- **If Lag High**: Check backpressure logs and CPU usage. Scale workers (manual).
