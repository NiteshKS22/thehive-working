# Phase E4.2 Runbook: Reliability Hardening

## Backpressure & Throttle
- **Max Poll Records**: Consumers are limited to 100 records per poll to prevent memory overload.
- **Backpressure**: If processing takes > 5s per batch, the consumer sleeps for 1s to allow downstream systems to recover.
- **Producer Queue**: If producer buffer is full, the consumer loop pauses.

## Retry Policy
- **Transient Failures** (Network, Timeout): Retry up to 3 times with exponential backoff (1s, 2s, 4s).
- **Permanent Failures** (Schema, Logic): DLQ immediately. No retry.
- **DLQ Failure**: If DLQ fails, consumer halts (no commit) to prevent data loss.

## Topic Retention
- **alerts.ingest.v1**: 7 days.
- **alerts.accepted.v1**: 7 days.
- **correlation.*.v1**: 30 days (audit trail).
- **cases.*.v1**: Infinite (compacted).
- **dlq.*.v1**: 30 days.

## Replay Procedures
See E4.1 Runbook for manual replay.
- **Burst Protection**: If lag > 1000, consumer will log warnings and process at max speed but limited by `max_poll_records`.

## Observability
- Logs will show `WARNING: Consumer lag is high: {lag}`.
- Logs will show `INFO: Backpressure active. Sleeping...`.
