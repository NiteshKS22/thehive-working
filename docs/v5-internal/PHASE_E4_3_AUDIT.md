# Phase E4.3 Audit: Observability & Health

## Target Services
| Service | Type | Health Ports | Metrics Port | Status |
|---------|------|--------------|--------------|--------|
| nv-ingest | HTTP | 8000 | 8000 | Pending |
| nv-query | HTTP | 8001 | 8001 | Pending |
| nv-case-engine | HTTP | 8002 | 8002 | Pending |
| nv-dedup | Worker | N/A | 9001 (Internal) | Pending |
| nv-indexer | Worker | N/A | 9002 (Internal) | Pending |
| nv-correlation | Worker | N/A | 9003 (Internal) | Pending |
| nv-group-indexer | Worker | N/A | 9004 (Internal) | Pending |

## Required Metrics
- consumer_lag
- messages_processed_total
- dlq_published_total
- retries_total
- backpressure_events_total
