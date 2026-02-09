# v5-Internal Architecture

## Mission
Decouple high-value SOC functions from the legacy monolith using the Strangler Fig Pattern.

## Componentization
- **Ingestion Layer**: Stateless, scalable services handling raw alerts.
- **Enrichment Layer**: Async workers for Cortex/Ollama integration.
- **Case Domain**: Core logic for case management (initially bridged to v4).
- **Storage**: Event-sourced or dual-write model initially.

## Adapter Layer
- **API Adapter**: Translates v5 internal events/calls to v4 legacy API calls where necessary.
- **Event Mirror**: Captures v4 events and publishes to v5 bus for shadow processing.

## Search Evolution
- **Current State**: Detected as Lucene/Elasticsearch (based on existing configs).
- **Target State**: OpenSearch or Elasticsearch 8.
- **Transition**: Dual-index writes during migration; read-path switchover once parity is confirmed.

## Backward Compatibility with v4-LTS
- No changes to v4 REST API contracts.
- v5 services run side-by-side.
- Data written by v5 is backward-compatible or synchronized back to v4 stores until cutover.
