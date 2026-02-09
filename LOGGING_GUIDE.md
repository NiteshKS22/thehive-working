# Logging & Troubleshooting Guide

## Log Locations

### Containerized Deployment
- **Application Logs**: STDOUT/STDERR. Accessible via `docker logs <container_id>`.
  - Format: Unstructured text (Logback default layout).
- **Access Logs**: Not enabled by default in Phase 0 config.

### Local Development
- Logs are output to the console where `sbt run` was executed.

## Common Error Patterns

### "Dependencies lock file is not found"
- **Cause**: CI workflow configuration expecting a lockfile when one isn't committed or generated.
- **Fix**: Ensure `npm ci` is used only when `package-lock.json` exists; otherwise fallback to `npm install`.

### "Cassandra/Elasticsearch not ready" during Startup
- **Symptom**: Application exits or restarts repeatedly.
- **Log Message**: `ConnectException: Connection refused`.
- **Fix**: Ensure dependent services are healthy. TheHive waits for Cassandra, but timeouts can occur on slow hardware. Increase `TH_CASSANDRA_BOOTSTRAP_TIMEOUT` if needed.

## Debugging Smoke Tests
CI artifacts include `docker-logs.txt` which captures the container output during the test run.
- **API Failures**: Check `tests/smoke_api/docker-logs.txt`.
- **UI Failures**: Check `playwright-report/` artifact for screenshots/videos.
