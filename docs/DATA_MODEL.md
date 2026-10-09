# Data Model

> **Status:** the Gold model is owner-approved (DEC-08, 2026-10-09); implementation is pending. Bronze, Silver, quarantine and `ops`
> are placeholders to be designed in D1-09. Everything here is design. Row counts are expectations derived from `docs/DATASET.md`, not
> measured Databricks results.
>
> Related: KPI formulas in [`docs/KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md) (DEC-03); tests and DQ checks in
> [`docs/TEST_STRATEGY.md`](TEST_STRATEGY.md) (DEC-10).

## 1. Bronze

*To be designed in D1-09.*

## 2. Silver and Quarantine

*To be designed in D1-09.*

## 3. ops (run audit and DQ results)

*To be designed in D1-09.* `ops.dq_results` is already specified by DEC-10 (see `docs/TEST_STRATEGY.md` §2).

## 4. Gold (DEC-08, owner-approved 2026-10-09)

One dimension plus four fact tables, each at exactly one grain.

| Table | Grain (key) | Columns | KPIs |
| ----- | ----------- | ------- | ---- |
| `gold.dim_ticker` | `ticker` | `ticker`, `bank_name`, `short_name`. 4 rows, loaded from a config file in the repo; names from `docs/DATASET.md` §1 | — |
| `gold.fact_daily_metrics` | `ticker`, `trade_date` | `close`, `adjclose`, `volume`, `volume_status`, `normalized_index`, `daily_return`, `vol_60d_ann`, `running_peak`, `drawdown`, `rel_volume_60d`, `year`, `month` | K1, K3, K4, K6, K10 |
| `gold.fact_monthly_metrics` | `ticker`, `month_start` | `monthly_return`, `avg_daily_volume`, `n_sessions`, `n_normal_sessions`, `is_partial` | K8, K11 |
| `gold.fact_yearly_metrics` | `ticker`, `year` | `yearly_return`, `n_sessions`, `is_partial` | K9 |
| `gold.ticker_summary` | `ticker` | `total_return`, `vol_full_ann`, `max_drawdown`, `peak_date`, `trough_date`, `current_drawdown`, `base_date`, `last_trade_date` | K2, K5, K7 |

### Common rules
- Every Gold table also has the lineage columns `source_run_id`, `source_ingested_at` (= `max(ingested_at_utc)` of the landed daily CSVs), `pipeline_run_id` and `built_at`.
- Full overwrite on every run (DEC-06).
- Gold rows start at the base date (`docs/KPI_DEFINITIONS.md` G3).
- **No partitioning or clustering:** about 7,500 daily rows in total (expected: 4 tickers × ~1,886 rows from the base date). *Recorded for REQ-22.*
- **No `dim_date`:** `year` and `month` are columns on the facts.

### Relationships
- Each fact joins `dim_ticker` on `ticker`.
- Facts are **not** joined to each other: one grain per table, one visual group per table.

### Dashboard date windows
- **v1 (MUST):** KPIs are shown for fixed periods (full period, calendar year, month). The global date filter applies to the time-series visuals.
- **SHOULD (attempted in D3 only if time allows):** a Unity Catalog SQL table function such as `gold.fn_window_performance(start_date, end_date)`,
  returning per ticker the window's total return, volatility and max drawdown, called by a parameterized dashboard dataset, so the KPI logic stays in Gold.
  **Unverified on Free Edition** (SQL table functions and AI/BI dashboard parameters). If unavailable, fall back to the MUST approach.

### Rationale
- Each question Q1–Q5 is answered by single-table queries (no fact-to-fact joins), so dashboard queries stay thin (filter and select).
- Each KPI lives in exactly one place, which keeps reconciliation (REQ-16) simple.
- A combined monthly/yearly table with a `period_type` column was **rejected** because it makes queries and key checks harder to read.
