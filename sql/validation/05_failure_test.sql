-- Induced-failure test verification (D2-09, DEC-13 option A). Procedure: docs/RUNBOOK.md.
-- Uses the catalog `workspace` and the default Volume paths literally (the project default in config/pipeline.json);
-- if the pipeline runs with another catalog (Job parameter `catalog`), replace `workspace` before running these queries.
-- Expected values assume the 2026-10-08 snapshot and that the last good run before the test is Job run 371194405323795
-- (docs/evidence/d2-07-rerun.md). To verify.

-- =====================================================================================================================
-- Section 1: after the FAILING run (landing_path = /Volumes/workspace/bronze/test_fixtures/failure_dup_key).
-- Replace <failed_run_id> with that Job run ID.
-- =====================================================================================================================

-- F1  Audit rows of the failing run.
-- Expected: bronze_ingest SUCCEEDED (rows_in = rows_out = 7548); silver_transform FAILED, error_message names
--           silver_no_duplicate_keys; NO gold_build row (the task was skipped). setup writes no audit row.
SELECT task_name, status, rows_in, rows_out, rows_rejected, error_message, started_at, ended_at
FROM workspace.ops.run_audit
WHERE job_run_id = '<failed_run_id>'
ORDER BY started_at;

-- F2  DQ results of the failing run.
-- Expected: 6 bronze checks, all passed; silver_no_duplicate_keys CRITICAL passed = false, failing_count = 1.
--           Other Silver checks are still recorded (they run before the raise); silver_same_date_set (WARN) is also expected to fail,
--           because the replaced row's date is missing for that ticker. No gold rows.
SELECT layer, check_name, severity, passed, failing_count, details
FROM workspace.ops.dq_results
WHERE pipeline_run_id = '<failed_run_id>'
ORDER BY layer, passed, check_name;

-- F3  Bronze now holds the fixture data (the window documented in docs/RUNBOOK.md).
-- Expected: duplicated_keys = 1; fixture_files = 4 (every source_file under the test_fixtures Volume).
SELECT
  (SELECT COUNT(*) FROM (SELECT ticker, source_date FROM workspace.bronze.daily_prices_raw
                         GROUP BY ticker, source_date HAVING COUNT(*) > 1))                       AS duplicated_keys,
  (SELECT COUNT(DISTINCT source_file) FROM workspace.bronze.daily_prices_raw
    WHERE source_file LIKE '%/Volumes/workspace/bronze/test_fixtures/%')                           AS fixture_files;

-- F4  Silver and Gold untouched: still the last good run, with unchanged row counts.
-- Expected: every row shows pipeline_run_id = 371194405323795 (n_run_ids = 1) and
--           n_rows = 7548 (silver), 7544 (daily), 376 (monthly), 32 (yearly), 4 (summary), 4 (dim).
SELECT 'silver.daily_prices' AS table_name, COUNT(*) AS n_rows, COUNT(DISTINCT pipeline_run_id) AS n_run_ids, MIN(pipeline_run_id) AS pipeline_run_id FROM workspace.silver.daily_prices
UNION ALL SELECT 'gold.fact_daily_metrics',   COUNT(*), COUNT(DISTINCT pipeline_run_id), MIN(pipeline_run_id) FROM workspace.gold.fact_daily_metrics
UNION ALL SELECT 'gold.fact_monthly_metrics', COUNT(*), COUNT(DISTINCT pipeline_run_id), MIN(pipeline_run_id) FROM workspace.gold.fact_monthly_metrics
UNION ALL SELECT 'gold.fact_yearly_metrics',  COUNT(*), COUNT(DISTINCT pipeline_run_id), MIN(pipeline_run_id) FROM workspace.gold.fact_yearly_metrics
UNION ALL SELECT 'gold.ticker_summary',       COUNT(*), COUNT(DISTINCT pipeline_run_id), MIN(pipeline_run_id) FROM workspace.gold.ticker_summary
UNION ALL SELECT 'gold.dim_ticker',           COUNT(*), COUNT(DISTINCT pipeline_run_id), MIN(pipeline_run_id) FROM workspace.gold.dim_ticker;

-- =====================================================================================================================
-- Section 2: after the RECOVERY run (a new run with the real landing_path; see docs/RUNBOOK.md).
-- Replace <recovery_run_id> with that Job run ID.
-- =====================================================================================================================

-- R1  Audit rows of the recovery run.
-- Expected: 3 rows (bronze_ingest, silver_transform, gold_build), all SUCCEEDED.
SELECT task_name, status, rows_in, rows_out, rows_rejected, error_message
FROM workspace.ops.run_audit
WHERE job_run_id = '<recovery_run_id>'
ORDER BY started_at;

-- R2  Bronze restored from the real landing Volume.
-- Expected: duplicated_keys = 0; fixture_files = 0; real_files = 4.
SELECT
  (SELECT COUNT(*) FROM (SELECT ticker, source_date FROM workspace.bronze.daily_prices_raw
                         GROUP BY ticker, source_date HAVING COUNT(*) > 1))                       AS duplicated_keys,
  (SELECT COUNT(DISTINCT source_file) FROM workspace.bronze.daily_prices_raw
    WHERE source_file LIKE '%/Volumes/workspace/bronze/test_fixtures/%')                           AS fixture_files,
  (SELECT COUNT(DISTINCT source_file) FROM workspace.bronze.daily_prices_raw
    WHERE source_file LIKE '%/Volumes/workspace/bronze/landing/%')                                 AS real_files;

-- R3  Gold rebuilt by the recovery run, with the same KPI values as before the test.
-- Expected: pipeline_run_id = <recovery_run_id> for all 4 rows; abs_diff = 0 for BBCA, BBRI and BMRI against docs/evidence/d2-05-gold.md.
--           BBNI's recorded value was truncated in a screenshot, so its abs_diff is only expected to be < 1e-16.
WITH expected AS (
  SELECT * FROM VALUES
    ('BBCA', 0.4096571841753591D),
    ('BBNI', 0.0949590457301969D),
    ('BBRI', 0.4301591927421744D),
    ('BMRI', 0.7596948888403188D) AS e(ticker, expected_total_return)
)
SELECT g.ticker, g.pipeline_run_id, g.total_return, e.expected_total_return,
       ABS(g.total_return - e.expected_total_return) AS abs_diff
FROM workspace.gold.ticker_summary g
JOIN expected e ON g.ticker = e.ticker
ORDER BY g.ticker;
