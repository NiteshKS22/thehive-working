# Migration Strategy

## Capability Mapping
**Priority 1**: Alert Ingestion.
- High volume, stateless, easy to decouple.

## Dual-Write / Mirror Logic
1. **Shadow Mode**: v5 receives mirrored traffic (e.g., via gateway or v4 hooks). Process but do not persist/act (or persist to shadow store).
2. **Dual-Write**: v5 persists to new store AND syncs to v4.
3. **Read-Path Switch**: Clients read from v5; v4 is backup.

## Cutover Gates
- **Latency**: v5 p99 < v4 p99.
- **Error Rate**: < 0.1%.
- **Data Parity**: 100% match on sample sets.
- **Workflow Parity**: Analysts can perform all ingest actions.

## Backward Compatibility with v4-LTS
- Migration is invisible to v4 API consumers.
- Rollback involves routing traffic back to v4-only path.
