-- Dataset: ds_monthly
-- Purpose: monthly returns (K8) and average daily volume over normal sessions (K11) per bank, with session counts and the partial-period flag.
-- Grain:   one row per ticker and month_start (376 rows for the 2026-10-08 snapshot).
-- Source:  gold.fact_monthly_metrics. Gold only; no KPI formulas here.
-- Used by: V8 monthly-return table, V9 average daily volume (dashboards/DASHBOARD_SPEC.md); filtered by ticker and the month_start range.
-- Note:    uses the catalog `workspace` literally; replace it if the pipeline runs with another catalog.
SELECT
  ticker,
  month_start,
  monthly_return,
  avg_daily_volume,
  n_sessions,
  n_normal_sessions,
  is_partial
FROM workspace.gold.fact_monthly_metrics
ORDER BY ticker, month_start
