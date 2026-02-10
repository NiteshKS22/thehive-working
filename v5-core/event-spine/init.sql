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
