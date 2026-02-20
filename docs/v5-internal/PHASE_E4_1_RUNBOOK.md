# Phase E4.1 Runbook: Reliability & DLQ

## Commit Strategy
All consumers (Dedup, Indexer, Correlation) use Manual Commit.
- **Success**: Process -> Flush -> Commit.
- **Logic Error**: DLQ -> Flush -> Commit.
- **Infra Error (DB/ES down)**: Retry loop (No Commit).
- **DLQ Error**: Retry loop (No Commit).

## Inspecting DLQ
DLQ topics contain JSON payloads with:
- `reason`: Why it failed.
- `original_message`: The raw Kafka message.
- `source_topic`: Origin.

### View DLQ Messages
```bash
rpk topic consume alerts.ingest.dlq.v1 --num 5
```

## Replay Strategy
1. Fix the root cause (bug or downstream service).
2. Consume from DLQ topic.
3. Republish `original_message` payload to `source_topic`.
   - Ensure `original_event_id` is preserved to maintain idempotency.

## Alerts
- **High**: Consumer lag increasing > 1000.
- **Critical**: DLQ topic incoming rate > 0.
