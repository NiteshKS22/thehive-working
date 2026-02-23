-- Phase B1.3: Additive Inbox Table for v5 -> v4 Bridge
-- Applied to v4 Database

CREATE TABLE IF NOT EXISTS v4_inbox (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'v5',
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'INFLIGHT', 'APPLIED', 'FAILED', 'CONFLICT', 'DLQ')),
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_v4_inbox_dedupe ON v4_inbox (tenant_id, entity_type, entity_id, source_event_id);
CREATE INDEX IF NOT EXISTS idx_v4_inbox_status_updated ON v4_inbox (status, updated_at);
CREATE INDEX IF NOT EXISTS idx_v4_inbox_tenant_status ON v4_inbox (tenant_id, status, updated_at);
