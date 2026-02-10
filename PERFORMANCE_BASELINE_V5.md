# v5 Performance Baselines

## Targets
| Metric | Target | Notes |
|--------|--------|-------|
| **Ingestion Latency** | < 200ms (P99) | Time from POST to Event Published ACK. |
| **Throughput** | > 1000 events/sec | Single instance, standard hardware. |
| **Event Propagation** | < 50ms | Time from Publisher to Subscriber. |

## Measuring
```bash
# Load Test using k6 or locust (future)
# Current Smoke Test:
time curl -X POST http://localhost:8000/ingest ...
```
