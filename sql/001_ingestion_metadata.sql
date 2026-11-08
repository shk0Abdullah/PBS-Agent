-- Provenance and audit tables only. Source-specific education tables belong in
-- later migrations after their workbook layouts have been flattened explicitly.

BEGIN;

CREATE SCHEMA IF NOT EXISTS ingestion;

CREATE TABLE ingestion.source_file (
    source_file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    relative_path TEXT NOT NULL UNIQUE,
    sha256 CHAR(64) NOT NULL,
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    worksheet_name TEXT NOT NULL,
    source_table_label TEXT,
    reporting_period_label TEXT,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    canonical_source_file_id BIGINT REFERENCES ingestion.source_file (source_file_id),
    CHECK (sha256 ~ '^[0-9A-F]{64}$'),
    CHECK (
        canonical_source_file_id IS NULL
        OR canonical_source_file_id <> source_file_id
    )
);

CREATE INDEX source_file_sha256_idx ON ingestion.source_file (sha256);

CREATE TABLE ingestion.import_run (
    import_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_id BIGINT NOT NULL
        REFERENCES ingestion.source_file (source_file_id) ON DELETE RESTRICT,
    importer_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'started'
        CHECK (status IN ('started', 'succeeded', 'failed')),
    rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
    rows_inserted INTEGER NOT NULL DEFAULT 0 CHECK (rows_inserted >= 0),
    rows_rejected INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    error_summary TEXT,
    CHECK (completed_at IS NULL OR completed_at >= started_at),
    CHECK (
        status = 'started'
        OR completed_at IS NOT NULL
    )
);

CREATE INDEX import_run_source_file_idx
    ON ingestion.import_run (source_file_id, started_at DESC);

CREATE TABLE ingestion.rejected_row (
    rejected_row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_run_id BIGINT NOT NULL
        REFERENCES ingestion.import_run (import_run_id) ON DELETE CASCADE,
    worksheet_row_number INTEGER NOT NULL CHECK (worksheet_row_number > 0),
    raw_cells JSONB NOT NULL,
    rejection_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX rejected_row_import_run_idx
    ON ingestion.rejected_row (import_run_id, worksheet_row_number);

COMMIT;
