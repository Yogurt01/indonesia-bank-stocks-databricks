# D3-04 Clean-state reproduction (owner-reported)

> Run by the owner on 2026-10-10 between about 20:40 and 21:00 (UTC+07), following `docs/RUNBOOK.md` ("Reset for a clean-state run").
> Results are owner-reported; the coding agent has no Databricks access. The agent inspected the retaken screenshots.

## 1. Reset (`notebooks/95_reset_environment`, `confirm = RESET`)

Dropped **11 tables, 0 already absent**:

| Layer | Tables |
| ----- | ------ |
| Gold | `ticker_summary`, `fact_yearly_metrics`, `fact_monthly_metrics`, `fact_daily_metrics`, `dim_ticker` |
| Silver | `daily_prices_quarantine`, `daily_prices` |
| Bronze | `source_run_summary`, `daily_prices_raw` |
| ops | `dq_results`, `run_audit` |

Schemas and Volumes were kept (the landed files stayed in place). Output: **RESET DONE**.

## 2. Rebuild: Job run **994907076175214** (default parameters)

The Job rebuilt every table from the landed files. The `setup` task recreated the `ops` tables, which now contain only this run's history; earlier runs
are documented in `docs/evidence/`.

| Query | Result |
| ----- | ------ |
| Q1 (`01_bronze.sql`) | 4 × 1,887 rows; `n_runs = 1`; dates 2019-01-01 → 2026-10-08; 0 rescued rows |
| S1 (`02_silver.sql`) | normal BBCA 1,872 / BBNI 1,873 / BBRI 1,874 / BMRI 1,873; `zero_all_tickers` 13 each; `zero_partial` 2 / 1 / 0 / 1 |
| G1 (`03_gold.sql`) | `dim_ticker` 4, `fact_daily_metrics` 7,544, `fact_monthly_metrics` 376, `fact_yearly_metrics` 32, `ticker_summary` 4 |
| G6 (`03_gold.sql`) and R-D1 (`06_dashboard_reconciliation.sql`) | `total_return` Silver = Gold, abs_diff 0: BBCA 0.4096571841753591, BBNI 0.09495904573019698, BBRI 0.4301591927421744, BMRI 0.7596948888403188 |
| G9 (`03_gold.sql`) | Peak/trough dates identical to the DEC-14 rebuild: BBCA 2024-09-23 / 2026-06-08, BBNI 2019-04-18 / 2020-03-24, BBRI 2020-01-23 / 2020-05-18, BMRI 2019-07-15 / 2020-05-18; every peak row `normal` |
| R-D6 (`06_dashboard_reconciliation.sql`) | Identical to `docs/evidence/d3-03-dashboard-reconciliation.md` |
| All other queries in `sql/validation/01`–`03` and `06` | Matched their stated expected results (owner-confirmed) |

## 3. Dashboard

The dashboard was refreshed after the rebuild, and V1 showed the same values as before. The 10 screenshots in `docs/evidence/dashboard/` were **retaken**
with the final V4/V6 subtitles.

Agent inspection of the retaken screenshots:
- the V4 subtitle "Gaps = zero-volume days (holidays, vendor gaps) excluded from return statistics." and the V6 subtitle "Decline from the running peak
  since 2019-01-02; not reset to the filter start. Values are ≤ 0." are visible (04, 09);
- the "2026 (partial)" label in V7 is fully visible (04, 09);
- V1 shows the same values as the reconciliation evidence (02, 07);
- no email address, account name, workspace host or URL appears in any of the 10 images.

## What this verifies

- **Reproducibility (REQ-19):** starting from empty target tables (schemas and landed files kept), one Job run with default parameters rebuilds Bronze,
  Silver and Gold with the same row counts, flags, KPIs and peak/trough dates as before, and the dashboard shows the same values.
- The reset notebook drops exactly the 11 documented tables and nothing else.
