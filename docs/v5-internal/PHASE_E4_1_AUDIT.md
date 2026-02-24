# Phase E4.1 Audit: Consumer Commit & DLQ Strategy

| Service | Input Topic(s) | DLQ Topic | Current Commit Strategy | Known Gaps |
|---------|----------------|-----------|-------------------------|------------|
| nv-dedup | alerts.ingest.v1 | alerts.ingest.dlq.v1 | Manual, not strictly enforced post-flush | Missing flush check |
| nv-indexer | alerts.accepted.v1 | alerts.indexer.dlq.v1 | Auto-commit (Risk) | Needs manual commit |
| nv-correlation | alerts.accepted.v1 | correlation.dlq.v1 | Manual | Check flush logic |
| nv-group-indexer | correlation.group.* | groups.indexer.dlq.v1 | Manual | Check flush logic |
| nv-case-engine | N/A (API only) | N/A | N/A | N/A |

**Action Items**:
1. Standardize `commit_if_safe` helper.
2. Update all workers to use helper.
3. Ensure `enable_auto_commit=False` everywhere.
