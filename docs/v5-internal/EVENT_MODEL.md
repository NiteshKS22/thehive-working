# Event Model

## Canonical Schema
JSON Schema definitions for core events:
- `AlertCreated`
- `CaseCreated`
- `ObservableAdded`
- `ObservableEnriched`
- `TaskUpdated`
- `ActionExecuted`

## Event Store Strategy
- **Append-Only**: Immutable log of all domain events.
- **Retention**: Configurable tiers (hot/warm/cold) for audit and replay.

## Observability
- **Trace-ID**: Propagated across all service boundaries.
- **Request-ID**: Client-provided or generated at ingress; logged in every structured log event.

## Backward Compatibility with v4-LTS
- v5 events map cleanly to v4 domain objects.
- v4-LTS remains the source of truth until specific modules are fully strangled.
