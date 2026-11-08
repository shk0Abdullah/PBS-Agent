BEGIN;

CREATE SCHEMA IF NOT EXISTS education;

CREATE TABLE education.table_01_school_participation (
    table_01_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file_id BIGINT NOT NULL
        REFERENCES ingestion.source_file (source_file_id) ON DELETE RESTRICT,
    import_run_id BIGINT NOT NULL
        REFERENCES ingestion.import_run (import_run_id) ON DELETE RESTRICT,
    worksheet_row_number INTEGER NOT NULL CHECK (worksheet_row_number >= 5),
    geography_name TEXT NOT NULL,
    area_type TEXT CHECK (area_type IN ('urban', 'rural')),
    gender TEXT CHECK (gender IN ('male', 'female')),
    ever_attended_pct NUMERIC(5, 2) NOT NULL
        CHECK (ever_attended_pct BETWEEN 0 AND 100),
    completed_primary_pct NUMERIC(5, 2) NOT NULL
        CHECK (completed_primary_pct BETWEEN 0 AND 100),
    out_of_school_pct NUMERIC(5, 2) NOT NULL
        CHECK (out_of_school_pct BETWEEN 0 AND 100),
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_file_id, worksheet_row_number)
);

CREATE INDEX table_01_geography_idx
    ON education.table_01_school_participation (geography_name, area_type, gender);

COMMENT ON TABLE education.table_01_school_participation IS
    'Flattened values from source Table 1; no joins to other source tables are implied.';

COMMIT;
