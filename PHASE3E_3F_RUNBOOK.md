# Phase 3E/3F Runbook: Analyst UI & Rule Governance

## Rule Governance

### Managing Rules
Rules are stored in the Postgres `correlation_rules` table.
Currently, rules are managed via SQL or by updating `init.sql` for new deployments.

#### Add a Rule
```sql
INSERT INTO correlation_rules (rule_id, rule_name, enabled, confidence, window_minutes, correlation_key_template, required_fields, created_at, updated_at)
VALUES ('R_NEW', 'New Rule', TRUE, 'MEDIUM', 30, '{tenant_id}|{field}', ARRAY['tenant_id', 'field'], 1700000000000, 1700000000000);
```
The Correlation Service automatically reloads rules every 60 seconds.

#### Disable a Rule
```sql
UPDATE correlation_rules SET enabled = FALSE WHERE rule_id = 'R_NEW';
```

#### Simulate a Rule
Use the `POST /rules/simulate` endpoint to test logic without creating groups.
```bash
curl -X POST "http://localhost:8001/rules/simulate?tenant_id=default"   -H "Content-Type: application/json"   -d '{"source": "test", "host": "server1", "rule_id": "R1_HOST_RULE"}'
```

## Analyst UI API

### Endpoints
- `GET /groups`: List groups (supports filtering by status).
- `GET /groups/{id}`: Get group details + rule metadata.
- `GET /groups/{id}/alerts`: Get alert timeline.
- `GET /rules`: List all rules.

### Troubleshooting
#### "Rule not matching"
1. Check if rule is enabled: `GET /rules`
2. Use Simulation endpoint with the exact alert payload.
3. Check Correlation Service logs for errors.

#### "Slow Rule Reload"
The worker reloads every `RULE_REFRESH_INTERVAL` (default 60s). Wait up to 1 minute after DB changes.
