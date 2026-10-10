-- Dataset: ds_yearly
-- Purpose: calendar-year returns (K9) per bank with the partial-period flag.
-- Grain:   one row per ticker and year (32 rows for the 2026-10-08 snapshot).
-- Source:  gold.fact_yearly_metrics. Gold only. year_label is presentation only (an axis label marking partial years), not a KPI formula.
-- Used by: V7 yearly-return grouped bar (dashboards/DASHBOARD_SPEC.md); filtered by ticker.
-- Note:    uses the catalog `workspace` literally; replace it if the pipeline runs with another catalog.
SELECT
  ticker,
  year,
  yearly_return,
  n_sessions,
  is_partial,
  CAST(year AS STRING) || CASE WHEN is_partial THEN ' (partial)' ELSE '' END AS year_label
FROM workspace.gold.fact_yearly_metrics
ORDER BY ticker, year
