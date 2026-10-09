# D2-01 Bronze ingestion (owner-reported)

> Run by the owner on 2026-10-09 between about 23:44 and 23:49 (UTC+07): notebook `notebooks/01_bronze_ingest` run **twice** interactively from
> the Databricks Git folder on serverless compute. Validation queries: [`sql/validation/01_bronze.sql`](../../sql/validation/01_bronze.sql).
> Results are owner-reported; the coding agent has no Databricks access and has not independently verified them.

## Notebook output

Both runs ended with **BRONZE PASS**: 6/6 checks passed (`bronze_all_tickers_present`, `bronze_header_matches`,
`bronze_rows_match_run_summary`, `bronze_source_symbol_matches`, `bronze_single_source_run_id`, `bronze_rescued_data_empty`).

## Validation queries (as reported)

| Query | Result |
| ----- | ------ |
| Q1 per-ticker rows | 4 × 1,887 rows; `n_runs = 1` after two runs (the overwrite is idempotent); dates 2019-01-01 → 2026-10-08; 0 rescued rows |
| Q3 rows for 2019-01-01 | Raw strings preserved (see the table below); `volume = 0` for all four; `ingested_at_utc` keeps the `+00:00` offset; `source_file` has the form `dbfs:/Volumes/workspace/bronze/landing/<folder>/<SYMBOL>.csv` |
| Q5 run audit | Two `SUCCEEDED` rows, `pipeline_run_id` `2a75f15c-72cf-4cee-96f9-a48831e1fcbc` and `30bc2666-467d-412c-bc5c-f7714bdfc9…` (truncated in the screenshot); `rows_in = rows_out = 7548`; `rows_rejected = 0`; `error_message` NULL |
| Q6 DQ results | 12 rows (2 runs × 6 checks), all `passed = true`, `failing_count = 0` |

Q3 values (raw strings as stored in Bronze):

| ticker | open | close | adjclose |
| ------ | ---- | ----- | -------- |
| BBCA | 5200.0 | 5200.0 | 4223.86279296875 |
| BBNI | — | 4400.0 | 3141.0419921875 |
| BBRI | — | 3327.215332031… | 2147.989501953… |
| BMRI | — | 3687.5 | 2288.6376953125 |

"—" means the value was not transcribed in the owner's report; "…" means it was truncated in the screenshot.

## What this verifies

- `_metadata.file_path` works with `spark.read` on serverless (the path has a `dbfs:` prefix; `folder_from_path` and the Spark `element_at(split(...), -2)` both handle it).
- `rescuedDataColumn` adds `_rescued_data` with an explicit schema, and it is empty for this snapshot.
- Raw values are preserved as strings (REQ-05); the row counts reconcile with `run-summary.json` and the local profile.
- `ops.run_audit` and `ops.dq_results` receive rows from the Bronze task (D2-02).
- A second run overwrites rather than appends (one `pipeline_run_id` remains in Bronze).

## Observation

The `adjclose / close` ratio on 2019-01-01 is 0.8123 (BBCA), 0.7139 (BBNI), 0.6456 (BBRI) and 0.6206 (BMRI). These equal the minimum ratios in
`docs/DATASET.md` §5, which confirms the "minimum ratio falls on the first date" assumption behind the illustrative total-return estimate
in `docs/KPI_DEFINITIONS.md` §5.

## Not verified by this run

- Running as a Job task, and `pipeline_run_id` from `{{job.run_id}}`.
- The CRITICAL failure path (raise before write, then a FAILED audit row). This is covered later by the induced-failure test (D2-09).
