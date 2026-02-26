# NeuralVyuha (formerly TheHive v5-Internal)

## Overview
**NeuralVyuha** is the next-generation Security Incident Response Platform (SIRP) engine, evolved from TheHive v5-Internal project. It is designed to be the "Neural System" of a modern Security Operations Center (SOC), providing high-performance ingestion, correlation, and case management capabilities.

This repository contains the complete source code for the NeuralVyuha engine (`nv-core`) alongside the legacy v4-LTS components it is designed to strangle and eventually replace.

## Key Features
*   **High-Volume Ingestion**: Stateless `nv-ingest` service capable of handling massive alert streams.
*   **Real-Time Correlation**: `nv-correlation` engine for grouping related alerts into meaningful incidents.
*   **Deduplication**: Redis-backed `nv-dedup` to reduce noise and alert fatigue.
*   **Unified Case Management**: `nv-case-engine` serves as the master of record for investigations.
*   **Legacy Compatibility**: Seamlessly integrates with existing v4 frontends via `reverse-bridge` synchronization.

## Architecture
The system is composed of several microservices orchestrated via the `nv-mesh` Docker network:

*   **nv-ingest**: Alert ingestion and validation.
*   **nv-dedup**: Alert deduplication and cross-correlation.
*   **nv-correlation**: Incident grouping logic.
*   **nv-case-engine**: Core domain logic for cases, tasks, and observables.
*   **nv-query**: Unified read API for dashboards and reports.
*   **nv-indexer**: OpenSearch indexing for fast search.

## Getting Started

### Prerequisites
*   Docker & Docker Compose
*   Python 3.10+ (for local development)
*   Java 8 (for legacy component builds)

### Running the Stack
To launch the full NeuralVyuha stack:

```bash
cd nv-core/event-spine
docker-compose up -d
```

This will start Redpanda (Kafka), Redis, Postgres, OpenSearch, and all core microservices.

### Documentation
Detailed documentation is available in the `docs/v5-internal/` directory:
*   [System State](docs/v5-internal/NEURALVYUHA_SYSTEM_STATE.md)
*   [Architecture](docs/v5-internal/ARCHITECTURE_V5_INTERNAL.md)
*   [Migration Guide](docs/v5-internal/ADR-035-GLOBAL-NAMESPACE-MIGRATION.md)

## License
This project is licensed under the AGPL-3.0 License. See [LICENSE](LICENSE) for details.

## Contact
For internal development inquiries, please refer to the internal engineering wiki.

### Legacy Development
To run the legacy TheHive application locally:
1. Ensure Java 8/11 is installed.
2. Run `./setup_dev.sh` to install dependencies and configure the application.
3. Run `./sbt run` to start the server on port 9000.
