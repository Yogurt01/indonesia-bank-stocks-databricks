-- Gold metadata validation (REQ-25): table and column comments applied by notebooks/03_gold_build.py from src/bank_pipeline/comments.py.
-- Uses the catalog `workspace` literally (the project default in config/pipeline.json); if the pipeline runs with another catalog
-- (Job parameter `catalog`), replace `workspace` before running these queries. Run after a successful Gold build.
-- Expected counts are derived from src/bank_pipeline/comments.py (5 table comments, 48 column comments) and the Gold column lists
-- in src/bank_pipeline/gold.py. To verify.

-- M1  Table comments in the gold schema.
-- Expected: 5 rows (dim_ticker, fact_daily_metrics, fact_monthly_metrics, fact_yearly_metrics, ticker_summary), each with a non-NULL comment
--           equal to TABLE_COMMENTS in comments.py.
SELECT table_name, comment
FROM workspace.information_schema.tables
WHERE table_schema = 'gold'
ORDER BY table_name;

-- M2  Column comments per Gold table.
-- Expected (n_columns / n_commented): dim_ticker 7 / 5; fact_daily_metrics 18 / 13; fact_monthly_metrics 11 / 9;
--           fact_yearly_metrics 9 / 8; ticker_summary 13 / 13. Total commented: 48.
-- Columns without a comment by design: dim_ticker bank_name, short_name; fact_daily_metrics close, adjclose, volume, year, month;
-- fact_monthly_metrics n_sessions, n_normal_sessions; fact_yearly_metrics n_sessions.
SELECT table_name,
       COUNT(*)       AS n_columns,
       COUNT(comment) AS n_commented
FROM workspace.information_schema.columns
WHERE table_schema = 'gold'
GROUP BY table_name
ORDER BY table_name;

-- M3  The column comments of ticker_summary (the table shown in the lineage screenshot).
-- Expected: 13 rows, all with a comment; e.g. total_return = 'K2: last adjclose / base-date adjclose - 1 (total return).'
SELECT column_name, comment
FROM workspace.information_schema.columns
WHERE table_schema = 'gold' AND table_name = 'ticker_summary'
ORDER BY ordinal_position;
