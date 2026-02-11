# Phase 3E/3F Audit Report

## C1: Offsets Commit Safety
- **STATUS**: BUG
- **EVIDENCE**: `v5-core/correlation-service/app/main.py`. `consumer.commit()` happens after loop, even if `process_correlation` failed and DLQ failed (if caught). `enable_auto_commit` is False, but logic commits batch even on partial failure.
- **ACTION**: Move commit to happen *per message* or track offsets strictly. For performance, we can commit batch only if ALL succeeded. Current logic `try...except...continue` swallows errors. Will update loop to `break` on critical failure or ensure successful DLQ before counting as processed.
- **TEST**: Code inspection.

## C2: Rules Tenant Scope
- **STATUS**: NOT A BUG (System Design Choice)
- **EVIDENCE**: `init.sql` defines `correlation_rules` without `tenant_id`.
- **REASONING**: Rules are global system definitions (templates) applied to all tenants. Tenant isolation happens at Group/Link creation time (using `tenant_id` from alert).
- **ACTION**: Added documentation note clarifying "Rules are Global".

## C3: Simulation Side Effects
- **STATUS**: NOT A BUG
- **EVIDENCE**: `v5-core/query-api-service/app/main.py` -> `simulate_rules`.
- **REASONING**: Calculates in-memory, returns JSON. No `producer.send` or `db.execute(INSERT)`.
- **ACTION**: None.

## C4: Reload Atomicity
- **STATUS**: NOT A BUG
- **EVIDENCE**: `RuleEngine.reload_rules` swaps `self.rules` reference. Python list assignment is atomic. Old list stays valid for active readers.
- **ACTION**: None.

## C5: Group Timeline Tenant Isolation
- **STATUS**: BUG (Minor/Strictness)
- **EVIDENCE**: `v5-core/query-api-service/app/main.py` -> `get_group_alerts`. Fetches docs from OpenSearch by ID without validating `doc['tenant_id'] == requested_tenant_id`.
- **REASONING**: While IDs are derived from Postgres links (which are tenant-safe), a compromised or buggy OpenSearch index could return data from another tenant if IDs collide or index is shared improperly.
- **ACTION**: Add explicit check: `if doc.get('tenant_id') != tenant_id: continue/raise`.
- **TEST**: Code inspection.
