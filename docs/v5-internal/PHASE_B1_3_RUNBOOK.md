# Phase B1.3 Runbook: Writeback Operations

## Enabling Writeback
Writeback is disabled by default. To enable:
1.  Set `V5_WRITEBACK_ENABLED=true` in v5-writeback-publisher.
2.  Set `V5_WRITEBACK_TENANTS=tenantA,tenantB` (allowlist).

## Rollback
To stop writeback immediately:
1.  Set `V5_WRITEBACK_ENABLED=false`.
2.  Stop `v4-inbox-applier`.

## Troubleshooting
-   **DLQ:** Check `bridge.v5.case.writeback.dlq.v1`.
-   **Conflicts:** Check `v4_inbox` table for `status='CONFLICT'`.
