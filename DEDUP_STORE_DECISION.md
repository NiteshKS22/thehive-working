# Dedup Store Decision Record

## Context
The Dedup & Correlation engine requires a persistent, high-performance store to track alert fingerprints and their state (first seen, count, correlation window) to ensure idempotency and noise reduction.

## Options Considered

### 1. PostgreSQL
- **Pros**: Strong consistency, relational model good for complex correlation rules, mature ecosystem.
- **Cons**: Higher latency for simple K/V checks compared to Redis, requires more complex cleanup (vacuum/partitioning) for high-volume transient data.

### 2. Redis
- **Pros**: Sub-millisecond latency, built-in TTL for automatic window expiry, atomic operations (SETNX, INCR), simple K/V model matches fingerprint lookups perfectly.
- **Cons**: Persistence (AOF/RDB) is robust but less "durable" in extreme crash scenarios than WAL-based DBs (acceptable for transient dedup windows).

## Decision
**Selected: Redis**

**Rationale**:
- **Performance**: Dedup is on the critical path of ingestion. Redis offers the lowest latency overhead.
- **Simplicity**: Built-in TTL handling eliminates the need for a separate "cleanup reaper" service.
- **Semantics**: Atomic counters and locks are native, making concurrent dedup straightforward.
- **Persistence**: We will enable AOF (Append Only File) persistence to ensure state survives container restarts, meeting the "Persistent Idempotency" requirement.

## Configuration
- **Mode**: Standalone (Phase 3B), Cluster (Phase 4+ if needed).
- **Persistence**: AOF enabled (`appendonly yes`).
- **Eviction**: `volatile-ttl` (though application should manage TTLs explicitly).
