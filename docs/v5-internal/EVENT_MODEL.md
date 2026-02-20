# Event Model

## Canonical Schema
JSON Schema definitions for core events:
- `AlertCreated`
- `CaseCreated`
- `ObservableAdded`
- `ObservableEnriched`
- `TaskUpdated`
- `ActionExecuted`

### Core Fields (Phase 3B Update)
- **`event_id`**: UUIDv4.
- **`trace_id`**: Distributed trace identifier.
- **`timestamp`**: Epoch millis.
- **`tenant_id`**: (Required) Identifies the tenant for multi-tenant isolation.
- **`schema_version`**: "1.0".
- **`payload`**: Domain-specific data (e.g., `Alert` object).

## Event Store Strategy
- **Append-Only**: Immutable log of all domain events.
- **Retention**: Configurable tiers (hot/warm/cold) for audit and replay.

## Observability
- **Trace-ID**: Propagated across all service boundaries.
- **Request-ID**: Client-provided or generated at ingress; logged in every structured log event.

## Backward Compatibility with v4-LTS
- v5 events map cleanly to v4 domain objects.
- v4-LTS remains the source of truth until specific modules are fully strangled.

## Correlation & Grouping Events (Phase 3D)

### CorrelationGroupCreated
- **Topic**: `correlation.group.created.v1`
- **Payload**:
  - `group_id`: Deterministic UUID/Hash based on key + time window.
  - `correlation_key`: The key that triggered the grouping.
  - `rule_id`, `rule_name`: Triggering rule metadata.
  - `confidence`: LOW/MEDIUM/HIGH.
  - `status`: OPEN.
  - `first_seen`, `last_seen`: Epoch timestamps.
  - `alert_count`: 1.
  - `max_severity`: Severity of first alert.
  - `tenant_id`: Mandatory tenant scope.

### CorrelationGroupUpdated
- **Topic**: `correlation.group.updated.v1`
- **Payload**:
  - `group_id`: Target group.
  - `status`: Current status (e.g., OPEN).
  - `last_seen`: Updated timestamp.
  - `alert_count`: Updated count.
  - `max_severity`: Updated severity.
  - `rule_name`: Triggering rule name (for context).
  - `tenant_id`: Mandatory tenant scope.

### AlertLinkedToGroup
- **Topic**: `correlation.alert.linked.v1`
- **Payload**:
  - `group_id`: Target group.
  - `original_event_id`: ID of the alert being linked.
  - `linked_at`: Timestamp of linking.
  - `link_reason`: Explanation (e.g., "Rule: Same host").
  - `tenant_id`: Mandatory tenant scope.

## Case Events (Phase E3)

### `cases.created.v1`
- **Type**: `CaseCreated`
- **Payload**: `{ case_id, title, created_by }`

### `cases.updated.v1`
- **Type**: `CaseUpdated`
- **Payload**: `{ case_id, updates, updated_by }`

### `cases.closed.v1`
- **Type**: `CaseClosed`
- **Payload**: `{ case_id, closed_by }`

### `cases.alert.linked.v1`
- **Type**: `CaseAlertLinked`
- **Payload**: `{ case_id, original_event_id }`
