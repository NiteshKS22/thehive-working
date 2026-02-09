# Performance Baselines

## Methodology
Baselines are established using the automated smoke test suite running in a consistent CI environment (2 vCPU, 7GB RAM runner).

## Benchmarks (v4-LTS Phase 1)

| Operation | Target Duration (P95) | Notes |
|-----------|-----------------------|-------|
| **Service Startup** | < 120s | Time until `/api/status` returns 200 OK. |
| **Login** | < 500ms | POST `/api/v1/login`. |
| **Create Case** | < 800ms | Empty case creation. |
| **Search Case** | < 1000ms | Simple text query on indexed fields. |
| **Add Observable** | < 1200ms | Adding a single IP observable. |

## Measuring Locally
Run the API smoke tests to get current timing feedback:
```bash
# Start stack
docker-compose -f tests/smoke_api/docker-compose.test.yml up -d

# Run tests
pytest tests/smoke_api/test_smoke.py --durations=0
```
