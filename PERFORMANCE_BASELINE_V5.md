# v5 Performance Baselines

## Targets
| Metric | Target | Notes |
|--------|--------|-------|
| **Ingestion Latency** | < 200ms (P99) | Time from POST to Event Published ACK. |
| **Dedup Latency** | < 10ms (P99) | Redis SETNX operation time. |
| **End-to-End Latency** | < 500ms | Ingest -> Dedup -> Accepted Event. |
| **Throughput** | > 1000 events/sec | Single instance, standard hardware. |

## Measuring
```bash
# Redis Latency
redis-cli --latency

# Consumer Lag
rpk group describe dedup-group-v1
```
