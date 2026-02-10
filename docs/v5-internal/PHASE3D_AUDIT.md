# Phase 3D Audit Report

## Issue A: AlertAccepted schema mismatch
- **Status**: NOT A BUG
- **Evidence**: `dedup-service` puts `tenant_id` at top level and `original_payload` inside payload. `correlation-service` reads `tenant_id` from event top level and `original_payload` from payload. This matches.
- **Action**: None.

## Issue B: DLQ not actually used
- **Status**: BUG
- **Evidence**: `correlation-service` defined DLQ topic but logged errors instead of publishing.
- **Action**: Implemented `producer.send(DLQ_TOPIC, ...)` for missing required fields or processing errors.
- **Test**: Code inspection.

## Issue C: Missing `type` field in correlation events
- **Status**: BUG
- **Evidence**: Output events lacked `type` field.
- **Action**: Added `type` field (e.g., `CorrelationGroupCreated`) to all producer outputs.
- **Test**: Code inspection.

## Issue D: v5 CI uses `--network host`
- **Status**: BUG
- **Evidence**: CI used host networking, hiding potential internal connectivity issues.
- **Action**: Switched CI to use `event-spine_default` network created by `docker-compose`. Services now communicate via internal DNS (redpanda, redis, postgres).
- **Test**: CI execution.

## Issue E: Smoke test JSON parsing is brittle
- **Status**: BUG
- **Evidence**: Bash substring matching.
- **Action**: Replaced with `.github/scripts/verify_smoke.py` using strict JSON parsing and assertion.
- **Test**: CI execution.

## Issue F: OpenSearch auth/security mode not explicit
- **Status**: NOT A BUG
- **Evidence**: Explicitly disabled via `DISABLE_SECURITY_PLUGIN=true` for development speed.
- **Action**: Documented this decision. Future phases (Production Hardening) will enable security.
