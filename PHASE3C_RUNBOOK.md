# Phase 3C Runbook: Indexing & Query

## Services
- **Indexer Worker**: Consumes `AlertAccepted`, writes to OpenSearch.
- **Query API**: Read-only API for searching alerts.

## Index Management
- **Pattern**: `alerts-v1-YYYY.MM`
- **Template**: `alerts-v1-template` (defined in `OPENSEARCH_INDEX_TEMPLATE.json`).
- **Rotation**: Monthly indices created automatically by the indexer.

## Operations

### Re-indexing
If mapping changes are needed:
1. Create new index template `v2`.
2. Stop indexer.
3. Update indexer config to write to `alerts-v2-*`.
4. Start indexer.
5. Backfill from Redpanda (replay) if needed.

### Troubleshooting

#### "Alerts not appearing in search"
1. Check `indexer-service` logs for errors (e.g. `MapperParsingException`).
2. Verify event reached `alerts.accepted.v1` topic.
3. Check OpenSearch health: `curl localhost:9200/_cluster/health`.

#### "Query API 500 Error"
- Check OpenSearch connectivity from the query pod.
- Check `tenant_id` filtering logic.

#### "Indexer Lag"
- Scale up indexer replicas (ensure same consumer group).
- Tune `bulk` size in indexer code.
