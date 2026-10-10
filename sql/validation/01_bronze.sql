-- Bronze validation queries (run in the Databricks SQL editor or a %sql cell).
-- Uses the catalog `workspace` and the default Volume paths literally (the project default in config/pipeline.json);
-- if the pipeline runs with another catalog (Job parameter `catalog`), replace `workspace` before running these queries.
-- Expected values are for the 2026-10-08 snapshot. Results of a run are recorded in docs/evidence/d2-01-bronze.md.

-- Q1  Per-ticker rows, runs, date range and rescued rows.
-- Expected: 4 rows (BBCA, BBNI, BBRI, BMRI), each n_rows = 1887, n_runs = 1 (overwrite is idempotent),
--           min_date = 2019-01-01, max_date = 2026-10-08, rescued_rows = 0.
SELECT
  ticker,
  COUNT(*)                                  AS n_rows,
  COUNT(DISTINCT pipeline_run_id)           AS n_runs,
  MIN(source_date)                          AS min_date,
  MAX(source_date)                          AS max_date,
  COUNT_IF(_rescued_data IS NOT NULL)       AS rescued_rows
FROM workspace.bronze.daily_prices_raw
GROUP BY ticker
ORDER BY ticker;

-- Q3  Rows for the first source date: raw strings must be preserved exactly as in the CSVs.
-- Expected: 4 rows; e.g. BBRI close = '3327.21533203125'; volume = '0' for all four (holiday row);
--           ingested_at_utc keeps its '+00:00' offset; source_file under /Volumes/workspace/bronze/landing/<folder>/.
SELECT *
FROM workspace.bronze.daily_prices_raw
WHERE source_date = '2019-01-01'
ORDER BY ticker;

-- Q5  Latest run-audit rows for the Bronze task.
-- Expected: status = 'SUCCEEDED', rows_in = rows_out = 7548, rows_rejected = 0, error_message NULL.
SELECT *
FROM workspace.ops.run_audit
WHERE task_name = 'bronze_ingest'
ORDER BY started_at DESC
LIMIT 5;

-- Q6  Latest Bronze DQ results.
-- Expected: 6 checks per run, all passed = true, failing_count = 0.
SELECT pipeline_run_id, check_name, severity, passed, failing_count, expected, details, checked_at
FROM workspace.ops.dq_results
WHERE layer = 'bronze'
ORDER BY checked_at DESC, check_name
LIMIT 12;
