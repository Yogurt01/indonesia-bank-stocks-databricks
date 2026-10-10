-- Dataset: ds_daily
-- Purpose: daily time series per bank: K1 normalized index (base 100 = base date), K3 daily return, K4 60-session volatility, K6 drawdown,
--          K10 relative volume, plus volume_status (flagged rows have NULL return statistics).
-- Grain:   one row per ticker and trade_date (7,544 rows for the 2026-10-08 snapshot).
-- Source:  gold.fact_daily_metrics. Gold only; no KPI formulas here.
-- Used by: V3 normalized index, V4 rolling volatility, V6 drawdown (dashboards/DASHBOARD_SPEC.md); filtered by ticker and the trade_date range.
-- Note:    uses the catalog `workspace` literally; replace it if the pipeline runs with another catalog.
SELECT
  ticker,
  trade_date,
  normalized_index,
  daily_return,
  vol_60d_ann,
  drawdown,
  rel_volume_60d,
  volume_status
FROM workspace.gold.fact_daily_metrics
ORDER BY ticker, trade_date
