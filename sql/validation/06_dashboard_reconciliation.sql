-- Dashboard reconciliation queries (D3-03, REQ-16, DASH-06).
-- Uses the catalog `workspace` and the default Volume paths literally (the project default in config/pipeline.json);
-- if the pipeline runs with another catalog (Job parameter `catalog`), replace `workspace` before running these queries.
-- Each KPI is recomputed INDEPENDENTLY from silver.daily_prices (not from Gold), following docs/KPI_DEFINITIONS.md; the matching Gold value and
-- abs_diff are shown next to it. Paste the dashboard value shown in the visual into docs/evidence/d3-03-dashboard-reconciliation.md.
-- Expected: abs_diff <= 1e-12 (R-D1, R-D2, R-D4, R-D5: the same doubles and operations) and <= 1e-9 (R-D3: stddev aggregation order may differ).
-- The dashboard shows percentages with 2 decimals, so "match" there means equal at the displayed precision.

-- R-D1  Total return (K2) per ticker. Compare with V1 and V2.
--       Base date found by the G3 rule (earliest date on which every ticker is 'normal'), not hard-coded; expected 2019-01-02.
WITH base AS (
  SELECT MIN(trade_date) AS base_date
  FROM (
    SELECT trade_date
    FROM workspace.silver.daily_prices
    GROUP BY trade_date
    HAVING COUNT_IF(volume_status = 'normal') = (SELECT COUNT(DISTINCT ticker) FROM workspace.silver.daily_prices)
  )
),
s AS (
  SELECT
    p.ticker,
    MAX_BY(p.adjclose, p.trade_date)                                 AS last_adjclose,
    MAX(CASE WHEN p.trade_date = b.base_date THEN p.adjclose END)    AS base_adjclose
  FROM workspace.silver.daily_prices p
  CROSS JOIN base b
  GROUP BY p.ticker
)
SELECT
  s.ticker,
  b.base_date,
  s.last_adjclose / s.base_adjclose - 1                          AS silver_total_return,
  g.total_return                                                 AS gold_total_return,
  ABS(s.last_adjclose / s.base_adjclose - 1 - g.total_return)    AS abs_diff
FROM s
CROSS JOIN base b
JOIN workspace.gold.ticker_summary g ON g.ticker = s.ticker
ORDER BY s.ticker;

-- R-D2  Max drawdown (K7) per ticker: running max of adjclose from the base date, minimum of adjclose / running max - 1. Compare with V1.
WITH base AS (
  SELECT MIN(trade_date) AS base_date
  FROM (
    SELECT trade_date
    FROM workspace.silver.daily_prices
    GROUP BY trade_date
    HAVING COUNT_IF(volume_status = 'normal') = (SELECT COUNT(DISTINCT ticker) FROM workspace.silver.daily_prices)
  )
),
dd AS (
  SELECT
    p.ticker,
    p.adjclose / MAX(p.adjclose) OVER (PARTITION BY p.ticker ORDER BY p.trade_date
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1 AS drawdown
  FROM workspace.silver.daily_prices p
  CROSS JOIN base b
  WHERE p.trade_date >= b.base_date
)
SELECT
  d.ticker,
  MIN(d.drawdown)                           AS silver_max_drawdown,
  g.max_drawdown                            AS gold_max_drawdown,
  ABS(MIN(d.drawdown) - g.max_drawdown)     AS abs_diff
FROM dd d
JOIN workspace.gold.ticker_summary g ON g.ticker = d.ticker
GROUP BY d.ticker, g.max_drawdown
ORDER BY d.ticker;

-- R-D3  Full-period volatility (K5) per ticker: daily returns on normal rows only, each from the previous NORMAL row (the WHERE runs before
--       the window), the base row has no previous row and drops out; stddev_samp x sqrt(252) (252 = kpi.annualization_factor in config).
--       Compare with V1 and V5.
WITH base AS (
  SELECT MIN(trade_date) AS base_date
  FROM (
    SELECT trade_date
    FROM workspace.silver.daily_prices
    GROUP BY trade_date
    HAVING COUNT_IF(volume_status = 'normal') = (SELECT COUNT(DISTINCT ticker) FROM workspace.silver.daily_prices)
  )
),
r AS (
  SELECT
    p.ticker,
    p.adjclose / LAG(p.adjclose) OVER (PARTITION BY p.ticker ORDER BY p.trade_date) - 1 AS daily_return
  FROM workspace.silver.daily_prices p
  CROSS JOIN base b
  WHERE p.trade_date >= b.base_date AND p.volume_status = 'normal'
)
SELECT
  r.ticker,
  STDDEV_SAMP(r.daily_return) * SQRT(252)                         AS silver_vol_full_ann,
  g.vol_full_ann                                                  AS gold_vol_full_ann,
  ABS(STDDEV_SAMP(r.daily_return) * SQRT(252) - g.vol_full_ann)   AS abs_diff
FROM r
JOIN workspace.gold.ticker_summary g ON g.ticker = r.ticker
GROUP BY r.ticker, g.vol_full_ann
ORDER BY r.ticker;

-- R-D4  Yearly return (K9) for BBCA 2022 = last adjclose of 2022 / last adjclose of 2021 - 1. Compare with V7 with the ticker filter = BBCA
--       (filtered-view check). Recorded Gold value: 0.19382545548113872 (docs/evidence/d2-05-gold.md).
WITH y AS (
  SELECT YEAR(trade_date) AS yr, MAX_BY(adjclose, trade_date) AS end_adjclose
  FROM workspace.silver.daily_prices
  WHERE ticker = 'BBCA' AND YEAR(trade_date) IN (2021, 2022)
  GROUP BY YEAR(trade_date)
),
s AS (
  SELECT MAX(CASE WHEN yr = 2022 THEN end_adjclose END) / MAX(CASE WHEN yr = 2021 THEN end_adjclose END) - 1 AS silver_yearly_return
  FROM y
)
SELECT
  'BBCA' AS ticker, 2022 AS year,
  s.silver_yearly_return,
  g.yearly_return                                   AS gold_yearly_return,
  ABS(s.silver_yearly_return - g.yearly_return)     AS abs_diff
FROM s
CROSS JOIN (SELECT yearly_return FROM workspace.gold.fact_yearly_metrics WHERE ticker = 'BBCA' AND year = 2022) g;

-- R-D5  Monthly return (K8) for BMRI 2020-03 = last adjclose of March 2020 / last adjclose of February 2020 - 1. Compare with V8
--       (ticker filter = BMRI, month range including 2020-03).
WITH m AS (
  SELECT TRUNC(trade_date, 'MM') AS month_start, MAX_BY(adjclose, trade_date) AS end_adjclose
  FROM workspace.silver.daily_prices
  WHERE ticker = 'BMRI' AND trade_date >= DATE'2020-02-01' AND trade_date < DATE'2020-04-01'
  GROUP BY TRUNC(trade_date, 'MM')
),
s AS (
  SELECT MAX(CASE WHEN month_start = DATE'2020-03-01' THEN end_adjclose END)
       / MAX(CASE WHEN month_start = DATE'2020-02-01' THEN end_adjclose END) - 1 AS silver_monthly_return
  FROM m
)
SELECT
  'BMRI' AS ticker, DATE'2020-03-01' AS month_start,
  s.silver_monthly_return,
  g.monthly_return                                   AS gold_monthly_return,
  ABS(s.silver_monthly_return - g.monthly_return)    AS abs_diff
FROM s
CROSS JOIN (SELECT monthly_return FROM workspace.gold.fact_monthly_metrics
            WHERE ticker = 'BMRI' AND month_start = DATE'2020-03-01') g;
