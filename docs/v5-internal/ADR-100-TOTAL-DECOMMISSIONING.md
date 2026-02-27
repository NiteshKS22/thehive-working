# ADR-100: Total Decommissioning of Legacy v4 Monolith

## Status
Accepted

## Context
The NeuralVyuha project has successfully migrated all core functionalities to the v5 microservices architecture. The legacy v4 monolith (Scala/Play) and the intermediate "Bridge" infrastructure are no longer required.

## Decision
1. **Delete** the entire `thehive/`, `cortex/`, `misp/` and related Scala source trees.
2. **Remove** the `v5-v4-reverse-bridge` service.
3. **Decommission** the v4 Frontend ("strangler fig" pattern complete) and replace it with a standalone `nv-ui`.
4. **Archive** legacy data migration scripts.

## Consequences
- **Positive**: Drastic reduction in codebase size, build time, and complexity. Scala dependency removed.
- **Negative**: No fallback path to v4. All data must be in v5 format.

## Compliance
This ADR satisfies the "CLEAN_PURGE" and "STANDALONE_UI" guardrails of Phase X1.
