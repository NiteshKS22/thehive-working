# Phase 3E/3F Audit Report

## C1: Offsets Commit Safety
- **STATUS**: BUG
- **EVIDENCE**: `neural-vyuha-engine/nv-correlation/app/main.py` original logic committed batch even if processing failed (swallowed exceptions) or if DLQ failed (not handled explicitly).
- **REASONING**: Committing offsets when data was not persisted or DLQ'd results in "At-Most-Once" delivery (data loss) on failure.
- **ACTION**: Updated loop to track `batch_success`. If processing error occurs AND DLQ publish fails, `batch_success` is set to `False` and `consumer.commit()` is skipped.
- **TEST**: `neural-vyuha-engine/nv-correlation/tests/test_offset_safety.py` validates that commit is skipped on DLQ failure.

## C2: Rules Tenant Scope
- **STATUS**: NOT A BUG
- **EVIDENCE**: `neural-vyuha-engine/event-spine/init.sql`. `correlation_rules` table does not have `tenant_id`.
- **REASONING**: Rules are global system templates (Phase 3F design). Tenant isolation is enforced during processing (Group creation is scoped by `tenant_id` from the alert).
- **ACTION**: Added documentation note in `PHASE3E_3F_RUNBOOK.md` clarifying that rules are global. No code change needed.
- **TEST**: Code inspection of `init.sql`.

## C3: Simulation Side Effects
- **STATUS**: NOT A BUG
- **EVIDENCE**: `neural-vyuha-engine/nv-query/app/main.py` -> `simulate_rules`.
- **REASONING**: Function only calculates matches in memory and returns JSON. It contains no `producer.send()` calls or DB `INSERT/UPDATE` statements.
- **ACTION**: None.
- **TEST**: Code inspection confirming absence of side effects.

## C4: Reload Atomicity
- **STATUS**: NOT A BUG
- **EVIDENCE**: `neural-vyuha-engine/nv-correlation/app/rules.py` uses `self.rules = new_rules`.
- **REASONING**: Python list assignment is atomic. Any running `evaluate` loop holds a reference to the old list and finishes safely. Next call picks up the new list.
- **ACTION**: None.
- **TEST**: Code inspection.

## C5: Group Timeline Tenant Isolation
- **STATUS**: BUG
- **EVIDENCE**: `neural-vyuha-engine/nv-query/app/main.py` -> `get_group_alerts` fetched docs from OpenSearch by ID and added them to response without checking `tenant_id`.
- **REASONING**: Defense-in-depth requires validating `tenant_id` on retrieved objects to prevent cross-tenant leakage if indices are corrupted or shared.
- **ACTION**: Added explicit check `if source.get("tenant_id") == tenant_id` before adding to results.
- **TEST**: `neural-vyuha-engine/nv-query/tests/test_isolation.py` proves mismatched tenants are filtered out.
