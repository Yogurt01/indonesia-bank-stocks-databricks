-- Silver validation queries (run in the Databricks SQL editor or a %sql cell).
-- Expected values are for the 2026-10-08 snapshot, derived from docs/DATASET.md and docs/KPI_DEFINITIONS.md §7; to verify.

-- S1  Per-ticker rows and volume_status counts.
-- Expected: n_rows = 1887 for each ticker; zero_all_tickers = 13 per ticker;
--           zero_partial: BBCA 2, BBNI 1, BMRI 1, BBRI 0 (so normal = 1872, 1873, 1873, 1874).
SELECT
  ticker,
  COUNT(*)                                        AS n_rows,
  COUNT_IF(volume_status = 'normal')              AS normal,
  COUNT_IF(volume_status = 'zero_all_tickers')    AS zero_all_tickers,
  COUNT_IF(volume_status = 'zero_partial')        AS zero_partial
FROM workspace.silver.daily_prices
GROUP BY ticker
ORDER BY ticker;

-- S2  Total rows and key uniqueness.
-- Expected: total_rows = 7548, distinct_keys = 7548.
SELECT
  COUNT(*)                                  AS total_rows,
  COUNT(DISTINCT ticker, trade_date)        AS distinct_keys
FROM workspace.silver.daily_prices;

-- S3  Quarantine count and reasons.
-- Expected: 0 rows (the table exists even when empty).
SELECT reject_reason, COUNT(*) AS n_rows
FROM workspace.silver.daily_prices_quarantine
GROUP BY reject_reason
ORDER BY n_rows DESC;

-- S4  zero_partial rows (ticker-specific vendor gaps, inferred).
-- Expected: 2020-03-13 BBCA, BBNI; 2020-03-16 BBCA, BMRI.
SELECT trade_date, ticker, open, high, low, close, volume
FROM workspace.silver.daily_prices
WHERE volume_status = 'zero_partial'
ORDER BY trade_date, ticker;

-- S5  Base date: earliest trade_date on which all 4 tickers are 'normal' (KPI rule G3).
-- Expected: 2019-01-02.
SELECT MIN(trade_date) AS base_date
FROM (
  SELECT trade_date
  FROM workspace.silver.daily_prices
  GROUP BY trade_date
  HAVING COUNT_IF(volume_status = 'normal') = 4
);

-- S6  Latest Silver DQ results.
-- Expected: 14 checks per run; all passed except silver_zero_partial_count (WARN, failing_count = 4, known vendor gaps);
--           silver_zero_all_tickers_count failing_count = 52; silver_base_date details = 'base_date=2019-01-02'.
SELECT pipeline_run_id, check_name, severity, passed, failing_count, expected, details, checked_at
FROM workspace.ops.dq_results
WHERE layer = 'silver'
ORDER BY checked_at DESC, check_name
LIMIT 14;

-- S7  Latest run-audit row for the Silver task.
-- Expected: status = 'SUCCEEDED', rows_in = 7548, rows_out = 7548, rows_rejected = 0, error_message NULL.
SELECT *
FROM workspace.ops.run_audit
WHERE task_name = 'silver_transform'
ORDER BY started_at DESC
LIMIT 3;
