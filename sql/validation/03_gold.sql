-- Gold validation queries (run in the Databricks SQL editor or a %sql cell).
-- Expected values are for the 2026-10-08 snapshot with base date 2019-01-02 (verified in docs/evidence/d2-03-silver.md);
-- the row counts are derived (1,887 rows minus 2019-01-01 = 1,886 per ticker; months 2019-01..2026-10 = 94; years 2019..2026 = 8). To verify.

-- G1  Row counts per table.
-- Expected: dim_ticker 4; fact_daily_metrics 7544 (4 x 1886); fact_monthly_metrics 376 (4 x 94);
--           fact_yearly_metrics 32 (4 x 8); ticker_summary 4.
SELECT 'dim_ticker' AS table_name, COUNT(*) AS n_rows FROM workspace.gold.dim_ticker
UNION ALL SELECT 'fact_daily_metrics',   COUNT(*) FROM workspace.gold.fact_daily_metrics
UNION ALL SELECT 'fact_monthly_metrics', COUNT(*) FROM workspace.gold.fact_monthly_metrics
UNION ALL SELECT 'fact_yearly_metrics',  COUNT(*) FROM workspace.gold.fact_yearly_metrics
UNION ALL SELECT 'ticker_summary',       COUNT(*) FROM workspace.gold.ticker_summary;

-- G2  Key uniqueness per table.
-- Expected: n_rows = n_keys for every table.
SELECT 'dim_ticker' AS table_name, COUNT(*) AS n_rows, COUNT(DISTINCT ticker) AS n_keys FROM workspace.gold.dim_ticker
UNION ALL SELECT 'fact_daily_metrics',   COUNT(*), COUNT(DISTINCT ticker, trade_date)  FROM workspace.gold.fact_daily_metrics
UNION ALL SELECT 'fact_monthly_metrics', COUNT(*), COUNT(DISTINCT ticker, month_start) FROM workspace.gold.fact_monthly_metrics
UNION ALL SELECT 'fact_yearly_metrics',  COUNT(*), COUNT(DISTINCT ticker, year)        FROM workspace.gold.fact_yearly_metrics
UNION ALL SELECT 'ticker_summary',       COUNT(*), COUNT(DISTINCT ticker)              FROM workspace.gold.ticker_summary;

-- G3  Ticker summary (K2, K5, K7).
-- Expected: 4 rows; base_date = 2019-01-02; last_trade_date = 2026-10-08; max_drawdown <= 0; peak_date <= trough_date;
--           one source_run_id (20261009T124332+0700). total_return differs from the illustrative estimates in
--           docs/KPI_DEFINITIONS.md §5, which start on 2019-01-01, not on the base date.
SELECT * FROM workspace.gold.ticker_summary ORDER BY ticker;

-- G4  Yearly returns (K9) with is_partial, plus the partial-period counts.
-- Expected: 8 years per ticker; is_partial TRUE for 2019 (first period) and 2026 (running) only.
SELECT ticker, year, yearly_return, n_sessions, is_partial
FROM workspace.gold.fact_yearly_metrics
ORDER BY ticker, year;

-- Expected: partial_months = 2 (2019-01 first, 2026-10 running) and partial_years = 2 for each ticker.
SELECT m.ticker, m.partial_months, y.partial_years
FROM (SELECT ticker, COUNT_IF(is_partial) AS partial_months FROM workspace.gold.fact_monthly_metrics GROUP BY ticker) m
JOIN (SELECT ticker, COUNT_IF(is_partial) AS partial_years  FROM workspace.gold.fact_yearly_metrics  GROUP BY ticker) y
  ON m.ticker = y.ticker
ORDER BY m.ticker;

-- G5  K4 leading NULLs: normal rows before the first non-NULL vol_60d_ann.
-- Expected: 60 per ticker.
WITH first_vol AS (
  SELECT ticker, MIN(trade_date) AS first_vol_date
  FROM workspace.gold.fact_daily_metrics
  WHERE vol_60d_ann IS NOT NULL
  GROUP BY ticker
)
SELECT d.ticker, COUNT(*) AS leading_null_normal_rows
FROM workspace.gold.fact_daily_metrics d
JOIN first_vol f ON d.ticker = f.ticker
WHERE d.volume_status = 'normal' AND d.trade_date < f.first_vol_date
GROUP BY d.ticker
ORDER BY d.ticker;

-- G6  Independent recomputation of total_return (K2) from Silver (seed of the REQ-16 reconciliation).
-- Expected: abs_diff <= 1e-9 for every ticker.
WITH s AS (
  SELECT
    ticker,
    MAX_BY(adjclose, trade_date)                                    AS last_adjclose,
    MAX(CASE WHEN trade_date = DATE'2019-01-02' THEN adjclose END)  AS base_adjclose
  FROM workspace.silver.daily_prices
  GROUP BY ticker
)
SELECT
  s.ticker,
  s.last_adjclose / s.base_adjclose - 1                     AS silver_total_return,
  g.total_return                                            AS gold_total_return,
  ABS(s.last_adjclose / s.base_adjclose - 1 - g.total_return) AS abs_diff
FROM s
JOIN workspace.gold.ticker_summary g ON s.ticker = g.ticker
ORDER BY s.ticker;

-- G7  Latest Gold DQ results.
-- Expected: 10 checks per run, all passed; gold_partial_periods (INFO) failing_count = 16 (4 tickers x (2 months + 2 years)).
SELECT pipeline_run_id, check_name, severity, passed, failing_count, expected, details, checked_at
FROM workspace.ops.dq_results
WHERE layer = 'gold'
ORDER BY checked_at DESC, check_name
LIMIT 10;

-- G8  Latest run-audit row for the Gold task.
-- Expected: status = 'SUCCEEDED', rows_in = 7548, rows_out = 7544, rows_rejected = 0, error_message NULL.
SELECT *
FROM workspace.ops.run_audit
WHERE task_name = 'gold_build'
ORDER BY started_at DESC
LIMIT 3;
