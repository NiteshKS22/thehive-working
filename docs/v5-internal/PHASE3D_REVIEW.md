# Phase 3D Review & Fixes

## Critical Bugs Fixed

### 1. Missing Partition Key in Correlation Producer
- **Issue**: `correlation-service` was sending events to `correlation.group.*` topics without a `key`.
- **Impact**: Events for the same group could land on different partitions. If a consumer (Group Indexer) reads partitions at different speeds, `GroupUpdated` could be processed before `GroupCreated`.
- **Result**: Partial documents created in OpenSearch (upsert=True), missing static fields like `rule_id`.
- **Fix**: Added `key=group_id.encode('utf-8')` to all `producer.send` calls in `correlation-service`.

## Logical Errors Fixed

### 1. Unsafe `updated_at` Logic
- **Issue**: `updated_at` in Postgres was blindly set to the incoming event timestamp.
- **Impact**: If events arrive out of order (late delivery), `updated_at` could jump backward in time, confusing the UI sorting.
- **Fix**: Changed SQL update to `updated_at = GREATEST(updated_at, %(last_seen)s)`.

## Observations (Not Bugs)

### 1. Simulation Timestamp
- **Observation**: The `/rules/simulate` API uses the current server time for window calculations.
- **Note**: Simulating historical alerts might produce different group IDs than if processed in real-time. This is a known limitation of the "Dry Run" feature.

### 2. Schema Duplication
- **Observation**: Rule logic is duplicated between `correlation-service` and `query-api-service` (simulation).
- **Note**: Accepted for Phase 3D to keep services decoupled without a shared library artifact pipeline. Logic is verified consistent.
