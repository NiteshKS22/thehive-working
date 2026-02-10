# Event Spine Decision Record

## Context
We need a persistent, high-throughput event log to serve as the backbone for v5 services. It must support replayability for audit/SOC needs and decoupling for the Strangler Fig pattern.

## Options Considered

### 1. Apache Kafka
- **Pros**: Industry standard, massive ecosystem, proven scale.
- **Cons**: JVM-heavy, requires ZooKeeper (or KRaft), complex ops for a sidecar deployment.

### 2. NATS JetStream
- **Pros**: Lightweight, single binary, built-in KV.
- **Cons**: Different semantics than Kafka (although getting closer), smaller ecosystem for data connectors compared to Kafka Connect.

### 3. Redpanda
- **Pros**: Kafka API compatible (drop-in replacement), single binary (C++), no JVM, highly performant, simpler ops (no ZK).
- **Cons**: Newer than Kafka, but stable for core use cases.

## Decision
**Selected: Redpanda**

**Rationale**:
- **Compatibility**: Allows us to use standard Kafka clients (librdkafka, python-kafka, etc.) which are mature.
- **Ops Simplicity**: Single binary container is ideal for our side-by-side deployment model with v4-LTS.
- **Performance**: High throughput with low latency suitable for alert ingestion.

## Configuration
- **Topic**: `alerts.ingest.v1`
- **Partitions**: 3 (default for reliability/parallelism)
- **Replication**: 1 (for single-node dev/CI), 3 (for production)
- **Retention**: 7 days (hot), then tiered storage to S3 (future).
