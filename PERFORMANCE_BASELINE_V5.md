# v5 Performance Baselines

## Targets
| Metric | Target | Notes |
|--------|--------|-------|
| **Ingestion Latency** | < 200ms (P99) | Time from POST to Event Published ACK. |
| **Dedup Latency** | < 10ms (P99) | Redis SETNX operation time. |
| **Indexing Latency** | < 500ms (P95) | Time from Accepted Event to Searchable. |
| **Query Latency** | < 200ms (P95) | Simple term query response time. |
| **End-to-End Latency** | < 1s | Ingest -> Searchable. |

## Measuring
```bash
# Query Latency
time curl "http://localhost:8001/alerts?q=test&tenant_id=default"
```
