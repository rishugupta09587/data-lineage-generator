-- ============================================================
-- Data Lineage Generator — PostgreSQL Schema
-- ============================================================
-- Run this file against your PostgreSQL database to set up
-- all required tables, indexes, and constraints.
--
-- Usage:
--   psql -U <user> -d <database> -f schema.sql
--
-- For SQLite (development), the schema is auto-created by
-- SQLAlchemy's Base.metadata.create_all() on app startup.
-- ============================================================

-- Enable uuid generation (PostgreSQL only)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── DAGs Table ────────────────────────────────────────────────────────────
-- Stores metadata for each uploaded pipeline DAG.
-- Each upload is a separate record; re-uploads create new versions.
CREATE TABLE IF NOT EXISTS dags (
    id          TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name        TEXT        NOT NULL,
    description TEXT,
    version     INTEGER     NOT NULL DEFAULT 1,
    raw_json    JSONB,                              -- original upload payload
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Automatically update updated_at on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dags_updated_at
    BEFORE UPDATE ON dags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Nodes Table ───────────────────────────────────────────────────────────
-- Each row represents a node (dataset or transformation) in a DAG.
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    dag_id      TEXT        NOT NULL REFERENCES dags(id) ON DELETE CASCADE,
    node_id     TEXT        NOT NULL,               -- user-defined ID (e.g., "raw_orders")
    name        TEXT        NOT NULL,               -- display name
    type        TEXT        NOT NULL                -- source | transformation | sink
                            CHECK (type IN ('source', 'transformation', 'sink')),
    operation   TEXT,                               -- filter | join | aggregation | etc.
    description TEXT,
    schema_info JSONB,                              -- column-level metadata
    tags        JSONB,                              -- array of string tags
    version     TEXT,                               -- dataset version/timestamp
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dag_node UNIQUE (dag_id, node_id)
);

-- Fast DAG-level lookups
CREATE INDEX IF NOT EXISTS ix_nodes_dag_id ON nodes (dag_id);
-- Full-text search on node name/description
CREATE INDEX IF NOT EXISTS ix_nodes_name_gin ON nodes USING GIN (to_tsvector('english', name));

-- ── Edges Table ───────────────────────────────────────────────────────────
-- Directed edges: from_node → to_node (data flows FROM to TO)
CREATE TABLE IF NOT EXISTS edges (
    id                TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    dag_id            TEXT        NOT NULL REFERENCES dags(id) ON DELETE CASCADE,
    from_node         TEXT        NOT NULL,
    to_node           TEXT        NOT NULL,
    relationship_type TEXT,                         -- e.g., "produces", "filters_into"
    column_mapping    JSONB,                        -- {source_col: target_col}
    CONSTRAINT uq_dag_edge UNIQUE (dag_id, from_node, to_node)
);

CREATE INDEX IF NOT EXISTS ix_edges_dag_id    ON edges (dag_id);
CREATE INDEX IF NOT EXISTS ix_edges_from_node ON edges (dag_id, from_node);
CREATE INDEX IF NOT EXISTS ix_edges_to_node   ON edges (dag_id, to_node);

-- ── Lineage Cache Table ───────────────────────────────────────────────────
-- Caches computed lineage results to avoid redundant graph traversals.
-- Cache key: (dag_id, node_id, lineage_type)
-- Invalidated on DAG re-upload or explicit delete.
CREATE TABLE IF NOT EXISTS lineage_cache (
    id            TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    dag_id        TEXT        NOT NULL,
    node_id       TEXT        NOT NULL,
    lineage_type  TEXT        NOT NULL               -- upstream|downstream|full|impact
                              CHECK (lineage_type IN ('upstream', 'downstream', 'full', 'impact')),
    result_json   JSONB       NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lineage_cache UNIQUE (dag_id, node_id, lineage_type)
);

CREATE INDEX IF NOT EXISTS ix_cache_dag_node ON lineage_cache (dag_id, node_id);

-- ── Metadata Table (optional enrichment) ─────────────────────────────────
-- For storing additional pipeline-level metadata (owners, SLAs, quality)
CREATE TABLE IF NOT EXISTS pipeline_metadata (
    dag_id       TEXT        NOT NULL REFERENCES dags(id) ON DELETE CASCADE,
    key          TEXT        NOT NULL,
    value        TEXT,
    value_json   JSONB,
    PRIMARY KEY (dag_id, key)
);

-- ── View: DAG Summary ─────────────────────────────────────────────────────
-- Convenience view joining dag + node/edge counts
CREATE OR REPLACE VIEW dag_summary AS
SELECT
    d.id           AS dag_id,
    d.name,
    d.version,
    d.created_at,
    COUNT(DISTINCT n.id)   AS node_count,
    COUNT(DISTINCT e.id)   AS edge_count
FROM dags d
LEFT JOIN nodes n ON n.dag_id = d.id
LEFT JOIN edges e ON e.dag_id = d.id
GROUP BY d.id, d.name, d.version, d.created_at;

-- ── Sample Data (dev/test only) ───────────────────────────────────────────
-- Uncomment to load a tiny example pipeline for quick testing:
/*
INSERT INTO dags (id, name, description, version) VALUES
    ('sample-001', 'Sample E-Commerce Pipeline', 'Demo pipeline', 1);

INSERT INTO nodes (dag_id, node_id, name, type, operation) VALUES
    ('sample-001', 'raw_orders',    'Raw Orders',       'source',         'read'),
    ('sample-001', 'clean_orders',  'Clean Orders',     'transformation', 'filter'),
    ('sample-001', 'revenue_agg',   'Revenue Agg',      'transformation', 'aggregation'),
    ('sample-001', 'revenue_rpt',   'Revenue Report',   'sink',           'write');

INSERT INTO edges (dag_id, from_node, to_node) VALUES
    ('sample-001', 'raw_orders',   'clean_orders'),
    ('sample-001', 'clean_orders', 'revenue_agg'),
    ('sample-001', 'revenue_agg',  'revenue_rpt');
*/
