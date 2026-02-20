# Bridge Event Model (Phase B1)

## Overview
This document defines the contract for events flowing between v4-LTS (Legacy) and v5-Internal via the Strangler Bridge. These events are used to synchronize state bi-directionally.

## Event Versioning
All bridge events are versioned starting at `v1`. Breaking changes require a new major version (e.g., `v2`).

## Common Envelope
All bridge events MUST follow this envelope:
```json
{
  "event_id": "UUID (v4)",
  "type": "EventTypeString",
  "trace_id": "UUID (v4) - Propagated or Generated",
  "tenant_id": "String (Required) - Authoritative Source Only",
  "timestamp": "Long (Epoch Millis)",
  "schema_version": "1.0",
  "payload": { ... }
}
```

## Events (v4 -> v5)

### `case.sync.v1`
Emitted when a Case is created or updated in v4.

**Topic:** `bridge.v4.case.sync.v1`

**Payload:**
```json
{
  "case_id": "String (v4 ID)",
  "title": "String",
  "description": "String (Optional)",
  "severity": "Integer (1-4)",
  "status": "String (Open, Resolved, Deleted)",
  "owner": "String",
  "flag": "Boolean",
  "tlp": "Integer (0-3)",
  "pap": "Integer (0-3)",
  "created_at": "Long (Epoch Millis)",
  "updated_at": "Long (Epoch Millis) - Used for Conflict Resolution",
  "custom_fields": { ... }
}
```

### `alert.sync.v1`
Emitted when an Alert is created or updated in v4.

**Topic:** `bridge.v4.alert.sync.v1`

**Payload:**
```json
{
  "alert_id": "String (v4 ID)",
  "title": "String",
  "type": "String",
  "source": "String",
  "sourceRef": "String",
  "status": "String (New, Updated, Ignored, Imported)",
  "created_at": "Long",
  "updated_at": "Long"
}
```

## Conflict Resolution Strategy
- **Writer Wins:** v5 Sync Service uses `GREATEST(existing.updated_at, incoming.updated_at)`.
- **v4 Authority:** In Phase B1, v4 is the system of record. If timestamps are equal, v4 wins.
- **Drift Logging:** Any state mismatch detected during sync (e.g., v5 has newer data but v4 overwrites) is logged to `bridge.drift.log`.

## Security
- **Tenant Isolation:** `tenant_id` is injected by the v4-Outbox-Publisher, which is a trusted component reading directly from the v4 DB context.
- **Validation:** v5 consumers MUST validate that `tenant_id` matches the target resource if it already exists.

## Drift Detection Strategy (Phase B1_4)

Drift detection is performed in two layers:

1.  **Inline (Real-time):** The `v4-sync-service` compares incoming event timestamps () against the current v5 state. If v5 is newer than the incoming v4 event, it logs a `DriftDetected` warning to the `bridge.drift.log.v1` topic. This prevents overwriting newer v5 data (though in Phase B1 v4 is authoritative).

2.  **Nightly Job (Batch):** A script `nightly_drift_check.py` performs a hash-based comparison.
    -   **Canonical Fields:** `case_id`, `title`, `status`, `severity`, `updated_at`.
    -   **Logic:** Fetches batches of v5 cases, retrieves authoritative state from v4 (mocked for initial implementation), computes SHA-256 hashes of the canonical fields, and alerts on mismatch.

## Drift Detection Strategy (Phase B1_4)

Drift detection is performed in two layers:

1.  **Inline (Real-time):** The `v4-sync-service` compares incoming event timestamps (`updated_at`) against the current v5 state. If v5 is newer than the incoming v4 event, it logs a `DriftDetected` warning to the `bridge.drift.log.v1` topic. This prevents overwriting newer v5 data (though in Phase B1 v4 is authoritative).

2.  **Nightly Job (Batch):** A script `nightly_drift_check.py` performs a hash-based comparison.
    -   **Canonical Fields:** `case_id`, `title`, `status`, `severity`, `updated_at`.
    -   **Logic:** Fetches batches of v5 cases, retrieves authoritative state from v4 (mocked for initial implementation), computes SHA-256 hashes of the canonical fields, and alerts on mismatch.
