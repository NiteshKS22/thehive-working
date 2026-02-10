-- Phase 3D Schema: Correlation Groups (Tenant-Isolated)

CREATE TABLE IF NOT EXISTS correlation_groups (
    tenant_id VARCHAR(64) NOT NULL,
    group_id VARCHAR(64) NOT NULL,
    correlation_key TEXT NOT NULL,
    rule_id VARCHAR(64) NOT NULL,
    rule_name TEXT,
    confidence VARCHAR(16) NOT NULL CHECK (confidence IN ('LOW', 'MEDIUM', 'HIGH')),
    status VARCHAR(16) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'MERGED')),
    first_seen BIGINT NOT NULL,
    last_seen BIGINT NOT NULL,
    alert_count INT NOT NULL DEFAULT 1,
    max_severity INT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    PRIMARY KEY (tenant_id, group_id)
);

CREATE INDEX IF NOT EXISTS idx_groups_tenant_key ON correlation_groups(tenant_id, correlation_key);
CREATE INDEX IF NOT EXISTS idx_groups_tenant_updated ON correlation_groups(tenant_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_groups_tenant_status ON correlation_groups(tenant_id, status);

CREATE TABLE IF NOT EXISTS correlation_group_alert_links (
    tenant_id VARCHAR(64) NOT NULL,
    group_id VARCHAR(64) NOT NULL,
    original_event_id VARCHAR(64) NOT NULL,
    linked_at BIGINT NOT NULL,
    link_reason TEXT,
    PRIMARY KEY (tenant_id, group_id, original_event_id),
    FOREIGN KEY (tenant_id, group_id) REFERENCES correlation_groups(tenant_id, group_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_links_tenant_alert ON correlation_group_alert_links(tenant_id, original_event_id);

-- Phase 3E/3F Schema: Rule Governance

CREATE TABLE IF NOT EXISTS correlation_rules (
    rule_id VARCHAR(64) PRIMARY KEY,
    rule_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    confidence VARCHAR(16) NOT NULL CHECK (confidence IN ('LOW', 'MEDIUM', 'HIGH')),
    window_minutes INT NOT NULL DEFAULT 15,
    correlation_key_template TEXT NOT NULL,
    required_fields TEXT[] NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

-- Seed Initial Rules
INSERT INTO correlation_rules (rule_id, rule_name, enabled, confidence, window_minutes, correlation_key_template, required_fields, created_at, updated_at)
VALUES
('R1_HOST_RULE', 'Same host + same rule_id', TRUE, 'HIGH', 15, '{tenant_id}|{host}|{rule_id}', ARRAY['tenant_id', 'host', 'rule_id'], 1700000000000, 1700000000000),
('R2_USER_AUTH', 'Auth anomalies by user', TRUE, 'HIGH', 10, '{tenant_id}|{user}|{auth_type}', ARRAY['tenant_id', 'user', 'auth_type'], 1700000000000, 1700000000000),
('R3_OBSERVABLE_HASH', 'Same observable hash', TRUE, 'MEDIUM', 30, '{tenant_id}|{observable_hash}|{observable_type}', ARRAY['tenant_id', 'observable_hash', 'observable_type'], 1700000000000, 1700000000000)
ON CONFLICT (rule_id) DO NOTHING;
