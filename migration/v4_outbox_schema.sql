-- Phase B1.1: Additive Outbox Table for v4 -> v5 Bridge
-- This schema is applied to the v4 Database (e.g. Postgres if v4 uses it, or adapted for Cassandra/ES if v4 is different)
-- Assumption: v4 DB is relational for this implementation scope.

CREATE TABLE IF NOT EXISTS v4_outbox (
    outbox_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL, -- CASE, ALERT
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL, -- case.sync.v1, alert.sync.v1
    event_version INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    trace_id TEXT,
    created_at BIGINT NOT NULL,
    available_at BIGINT NOT NULL, -- Scheduled publish time (default = created_at)
    published_at BIGINT,
    publish_attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'INFLIGHT', 'PUBLISHED', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_v4_outbox_status_available ON v4_outbox (status, available_at);
CREATE INDEX IF NOT EXISTS idx_v4_outbox_agg ON v4_outbox (tenant_id, aggregate_type, aggregate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_v4_outbox_published_at ON v4_outbox (published_at);

-- Constraint to ensure uniqueness of event if needed, though UUID is primary.
-- UNIQUE (tenant_id, aggregate_type, aggregate_id, event_type, created_at, outbox_id);
