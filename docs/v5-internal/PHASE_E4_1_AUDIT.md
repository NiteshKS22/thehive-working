# Phase E4.1 Audit: Consumer Commit & DLQ Strategy

| Service | Input Topic(s) | DLQ Topic | Current Commit Strategy | Known Gaps |
|---------|----------------|-----------|-------------------------|------------|
| dedup-correlation-service | alerts.ingest.v1 | alerts.ingest.dlq.v1 | Manual, not strictly enforced post-flush | Missing flush check |
| opensearch-indexer-service | alerts.accepted.v1 | alerts.indexer.dlq.v1 | Auto-commit (Risk) | Needs manual commit |
| correlation-service | alerts.accepted.v1 | correlation.dlq.v1 | Manual | Check flush logic |
| group-indexer-service | correlation.group.* | groups.indexer.dlq.v1 | Manual | Check flush logic |
| case-service | N/A (API only) | N/A | N/A | N/A |

**Action Items**:
1. Standardize `commit_if_safe` helper.
2. Update all workers to use helper.
3. Ensure `enable_auto_commit=False` everywhere.
