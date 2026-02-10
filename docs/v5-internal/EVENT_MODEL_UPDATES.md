# Event Model Updates (Phase 3B)

## New Event Types

### `AlertAccepted`
Emitted when an alert is seen for the first time or falls outside the correlation window of previous alerts.
```json
{
  "event_id": "uuid",
  "trace_id": "uuid",
  "timestamp": 1234567890,
  "type": "AlertAccepted",
  "schema_version": "1.0",
  "payload": {
    "original_alert": { ... },
    "fingerprint": "hash_string",
    "decision": "accepted"
  }
}
```

### `AlertDuplicateRejected`
Emitted when an alert matches an existing fingerprint within the dedup window.
```json
{
  "event_id": "uuid",
  "trace_id": "uuid",
  "timestamp": 1234567890,
  "type": "AlertDuplicateRejected",
  "schema_version": "1.0",
  "payload": {
    "fingerprint": "hash_string",
    "original_event_id": "uuid_of_first_seen",
    "count": 5
  }
}
```

### `AlertCorrelated`
Emitted when an alert is grouped with an active case or alert group (stub for future logic).
```json
{
  "event_id": "uuid",
  "trace_id": "uuid",
  "timestamp": 1234567890,
  "type": "AlertCorrelated",
  "schema_version": "1.0",
  "payload": {
    "fingerprint": "hash_string",
    "parent_group_id": "uuid"
  }
}
```
