# Phase E4.3 Audit: Observability & Health

## Target Services
| Service | Type | Health Ports | Metrics Port | Status |
|---------|------|--------------|--------------|--------|
| alert-ingestion-service | HTTP | 8000 | 8000 | Pending |
| query-api-service | HTTP | 8001 | 8001 | Pending |
| case-service | HTTP | 8002 | 8002 | Pending |
| dedup-correlation-service | Worker | N/A | 9001 (Internal) | Pending |
| opensearch-indexer-service | Worker | N/A | 9002 (Internal) | Pending |
| correlation-service | Worker | N/A | 9003 (Internal) | Pending |
| group-indexer-service | Worker | N/A | 9004 (Internal) | Pending |

## Required Metrics
- consumer_lag
- messages_processed_total
- dlq_published_total
- retries_total
- backpressure_events_total
