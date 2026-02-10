# RBAC & Audit Model

## RBAC
- **Roles**: Granular permissions (e.g., `alert:create`, `case:read`).
- **Templates**: Pre-defined sets (Analyst, Admin, Read-Only).
- **Policy**: Evaluation based on User + Resource + Context.

## Audit
- **Immutability**: Write-once audit logs (WORM storage recommended).
- **Mapping**: Every Domain Event produces an Audit Event.
- **Export**: Standard JSON/CSV export for external compliance tools.

## Backward Compatibility with v4-LTS
- v5 RBAC maps to v4 profiles/roles where possible.
- Audit trails for v5 actions are distinct but can be correlated with v4 logs via Trace-ID.
