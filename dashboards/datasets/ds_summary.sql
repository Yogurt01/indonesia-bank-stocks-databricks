-- Dataset: ds_summary
-- Purpose: full-period KPIs per bank (K2 total return, K5 volatility, K7 max/current drawdown with peak and trough dates) plus the snapshot lineage.
-- Grain:   one row per ticker (4 rows).
-- Source:  gold.ticker_summary joined to gold.dim_ticker (display names). Gold only; no KPI formulas here (docs/KPI_DEFINITIONS.md).
-- Used by: V1 summary table, V2 total-return bar, V5 full-period volatility bar (dashboards/DASHBOARD_SPEC.md).
-- Note:    uses the catalog `workspace` literally (project default in config/pipeline.json); replace it if the pipeline runs with another catalog.
SELECT
  s.ticker,
  d.short_name,
  d.bank_name,
  s.total_return,
  s.vol_full_ann,
  s.max_drawdown,
  s.peak_date,
  s.trough_date,
  s.current_drawdown,
  s.base_date,
  s.last_trade_date,
  s.source_run_id,
  s.source_ingested_at
FROM workspace.gold.ticker_summary s
JOIN workspace.gold.dim_ticker d ON d.ticker = s.ticker
ORDER BY s.ticker
