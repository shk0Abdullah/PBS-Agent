# Education workbook ingestion design

## Scope and principles

The `edu/` workbooks are published aggregate tables, not a relational source
system and not student-level data. A visual row such as `Male` inherits the
province and (when applicable) area from preceding rows. It must be flattened
before it is stored or queried.

Each imported record retains its source workbook, worksheet row number, and
import-run ID. This lets the application explain a value and makes it possible
to re-import a corrected workbook without overwriting history. The files in
`edu/` are read-only inputs.

`ingestion.source_file`, `ingestion.import_run`, and `ingestion.rejected_row`
are shared audit tables. Each workbook then receives its own table in the
`education` schema. Tables are not joined merely because their labels resemble
one another. A curated query layer can be introduced later only for comparisons
whose compatible grain and definitions have been verified.

## Table 1: school participation measures

Source: `Table-1-Population-10-Year-and-older-that-has-Ever-Attended-School-completed-primary-and-out-of-school-by-Province-Region-and-Gender.xlsx`

Observed source columns:

| Workbook columns | Stored column | Meaning retained from source |
| --- | --- | --- |
| Province/Region/Gender | `geography_name`, `area_type`, `gender` | Hierarchical display label flattened to dimensions |
| Ever Attended (age >=10) | `ever_attended_pct` | Percentage |
| Completed Primary Level (age >=10) | `completed_primary_pct` | Percentage |
| Out of School children (age 5-16) | `out_of_school_pct` | Percentage |

The source has 45 data rows (worksheet rows 5–49) for Pakistan and four
provinces. `gender` and `area_type` are nullable deliberately: a null means the
source row is an aggregate label, not an invented `both` or `total` category.
The importer rejects a child row (`Male`, `Female`, `Urban`, or `Rural`) that
does not have an active geography context.

No relationship is asserted between Table 1 and Tables 2–19. The similarly
named out-of-school measures have different stated age ranges and must remain
separate until their definitions and grain are verified.

## Import sequence

1. Hash and register the workbook in `ingestion.source_file`.
2. Mark exact duplicate files through `canonical_source_file_id`; import a
   canonical file once.
3. Create an `ingestion.import_run` record.
4. Parse and validate the workbook without modifying it.
5. Insert its flattened records into its source-specific table in one
   transaction; record any rejected source rows.
6. Mark the run as succeeded only after row-count and range checks pass.

The next importer should follow this same sequence rather than copying Table 1
assumptions.
