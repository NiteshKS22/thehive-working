# ADR-035: Global Namespace Migration to NeuralVyuha

## Status
Accepted

## Context
The "TheHive NeuralVyuha" project is undergoing a strategic rebranding to "NeuralVyuha". This requires a comprehensive renaming of all technical artifacts, including directory structures, service names, container definitions, network identifiers, and data plane resources (Kafka topics, OpenSearch indices).

The goal is to eliminate all references to "v5", "TheHive", and "cortex" from the internal engine codebase (`neural-vyuha-engine`) to establishing a distinct identity and namespace that does not conflict with legacy v4 systems.

## Decision
We will execute a global namespace migration with the following specifications:

1.  **Directory Structure**:
    *   Rename `neural-vyuha-engine/` to `nv-core/`.
    *   Rename all service subdirectories to match the new `nv-` naming convention.

2.  **Service & Container Naming**:
    *   All Docker containers and services will use the `nv-` prefix.
    *   `nv-ingest` -> `nv-ingest`
    *   `nv-case-engine` -> `nv-case-engine`
    *   `nv-query` -> `nv-query`
    *   `nv-indexer` -> `nv-indexer`
    *   `nv-correlation` -> `nv-correlation`
    *   `nv-dedup` -> `nv-dedup`
    *   `nv-group-indexer` -> `nv-group-indexer`

3.  **Infrastructure**:
    *   Docker Network: `nv-mesh` (replacing `nv-mesh`).
    *   Postgres Database: `nv_vault` (replacing `nv_vault`).

4.  **Data Plane**:
    *   Kafka Topics: All topics must start with `nv.` (e.g., `nv.alerts.ingest`).
    *   OpenSearch Indices: All indices must start with `nv-` (e.g., `nv-alerts-v1-2023.10`).

5.  **Identity & Security**:
    *   JWT Audience: `neural-vyuha-engine`.
    *   Event Envelopes: `NeuralDLQEvent`.

## Consequences
*   **Isolation**: The new namespace ensures complete isolation from v4-LTS components.
*   **Clarity**: The "NeuralVyuha" brand is now reflected in the technical architecture.
*   **Breaking Changes**: Requires fresh deployment.
*   **CI/CD**: `v5-ci.yml` renamed to `nv-ci.yml`.
