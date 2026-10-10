# Dashboard specification: "Indonesian Bank Stocks - Performance and Risk"

> Build guide for a Databricks **AI/BI dashboard** (one page) on the Gold layer (D3-01/D3-02, REQ-15). KPI definitions: `docs/KPI_DEFINITIONS.md`
> (DEC-03, DEC-14). Data model: `docs/DATA_MODEL.md` §4. The datasets are thin `SELECT`s over Gold in `dashboards/datasets/`; no KPI is computed in the
> dashboard. Menu names below follow the AI/BI dashboard editor as described in Databricks documentation; any label that differs in the Free Edition UI
> should be noted in the evidence rather than worked around.

## 1. Datasets (Data tab → "Create from SQL")

Create one dataset per file and paste the file's SQL as is.

| Dataset | File | Grain | Used by |
| ------- | ---- | ----- | ------- |
| `ds_summary` | `dashboards/datasets/ds_summary.sql` | ticker (4 rows) | V1, V2, V5 |
| `ds_daily` | `dashboards/datasets/ds_daily.sql` | ticker × trade_date | V3, V4, V6 |
| `ds_monthly` | `dashboards/datasets/ds_monthly.sql` | ticker × month_start | V8, V9 |
| `ds_yearly` | `dashboards/datasets/ds_yearly.sql` | ticker × year | V7 |

## 2. Header text widget (top of the page)

```markdown
# Indonesian Bank Stocks - Performance and Risk
Descriptive comparison of BBCA, BBNI, BMRI and BBRI since 2019 - not investment advice.
**Data snapshot:** see `last_trade_date` and `source_run_id` in the summary table.
**Definitions:** total return uses `adjclose` (adjusted for dividends and corporate actions) · volatility = 60-session rolling standard deviation
of daily returns × √252 · drawdown = decline from the running peak · partial periods are flagged · zero-volume rows are excluded from return statistics.
```

## 3. Filters (page-level filter widgets)

| Filter | Type | Field(s) | Applies to |
| ------ | ---- | -------- | ---------- |
| Ticker | Multiple values | `ticker` in every dataset | All visuals (connect the filter to `ticker` of `ds_summary`, `ds_daily`, `ds_monthly`, `ds_yearly`) |
| Trade date | Date range | `ds_daily.trade_date` | V3, V4, V6 |
| Month | Date range | `ds_monthly.month_start` | V8, V9 |

**Important:** the summary KPIs (V1, V2, V5) and the yearly returns (V7) are **full-period / fixed-period values**. They do **not** change with the date
filters. Window KPIs (return, volatility or drawdown over an arbitrary date range) are the SHOULD table function `gold.fn_window_performance`, which is not
in v1 (DEC-08, `docs/DATA_MODEL.md` §4).

## 4. Visuals

Formatting for every return, volatility and drawdown field: **percent, 2 decimals**. `normalized_index`: number, 2 decimals. Volumes: number,
thousands separator, 0 decimals. Dates: `YYYY-MM-DD`.

| ID | Title | Dataset | Type | X | Y | Color / series | Formatting and notes | Question |
| -- | ----- | ------- | ---- | - | - | -------------- | -------------------- | -------- |
| V1 | Full-period summary | `ds_summary` | Table | — | Columns: `short_name`, `total_return`, `vol_full_ann`, `max_drawdown`, `peak_date`, `trough_date`, `current_drawdown`, `last_trade_date` | — | Percent (2 dp) for the 4 ratio columns; column headers: Bank, Total return, Volatility (ann.), Max drawdown, Peak date, Trough date, Current drawdown, Last trade date | Q1–Q3 |
| V2 | Total return since 2019-01-02 | `ds_summary` | Bar | `short_name` | `total_return` | — | Percent (2 dp); sort descending by Y | Q1 |
| V3 | Normalized price index (base 100 = 2019-01-02) | `ds_daily` | Line | `trade_date` | `normalized_index` | `ticker` | Subtitle: "Base 100 = 2019-01-02; not rebased to the filter start." | Q1 |
| V4 | Rolling volatility (60 sessions, annualized) | `ds_daily` | Line | `trade_date` | `vol_60d_ann` | `ticker` | Percent (2 dp). The first 60 sessions are empty by definition. | Q2 |
| V5 | Full-period volatility (annualized) | `ds_summary` | Bar | `short_name` | `vol_full_ann` | — | Percent (2 dp); sort descending | Q2 |
| V6 | Drawdown from running peak | `ds_daily` | Line (or area) | `trade_date` | `drawdown` | `ticker` | Percent (2 dp); values ≤ 0 | Q3 |
| V7 | Calendar-year return | `ds_yearly` | Grouped bar | `year_label` | `yearly_return` | `ticker` | Percent (2 dp); `year_label` marks partial years "(partial)" | Q4 |
| V8 | Monthly return | `ds_monthly` | Pivot table (or table) | Rows: `month_start` | Values: `monthly_return` | Columns: `ticker` | Percent (2 dp); add `is_partial` as a row field or a tooltip so partial months are visible | Q4 |
| V9 | Average daily volume per month (SHOULD) | `ds_monthly` | Line | `month_start` | `avg_daily_volume` | `ticker` | Number, 0 dp. Caption: "Compare each bank with itself over time, not levels across banks (share counts differ)." | Q5 |

## 5. Suggested layout (rows from top to bottom)

1. Header text widget (full width); filters to the right or in a filter bar.
2. V1 summary table (full width).
3. V2 total return (half) | V5 full-period volatility (half).
4. V3 normalized index (full width).
5. V4 rolling volatility (half) | V6 drawdown (half).
6. V7 calendar-year return (half) | V8 monthly return (half).
7. V9 average daily volume (full width, SHOULD).
8. Footer text widget: metric definitions.

Footer text widget:

```markdown
**Metric definitions** (full text: docs/KPI_DEFINITIONS.md in the project repository)
- Total return (K2) = last adjclose / adjclose on the base date (2019-01-02) - 1.
- Volatility (K4/K5) = sample standard deviation of daily returns on normal (traded) sessions × √252; K4 uses the last 60 sessions.
- Drawdown (K6) = adjclose / running peak - 1; max drawdown (K7) is its minimum; peak date = the day the peak was set.
- Monthly / yearly return (K8/K9) = period-end adjclose / previous period-end adjclose - 1; the first period starts at the base date.
- Partial = first period, or the period still running at the snapshot's last trade date.
```

## 6. Reproducibility

- Dataset SQL lives in `dashboards/datasets/`. If a dataset is edited in the UI, copy the change back to the file.
- Screenshots of the finished dashboard (full page, plus one filtered view) go to `docs/evidence/dashboard/`.
- If the UI offers an export of the dashboard definition (a `.lvdash.json` file), save it to `dashboards/`. **Unverified on Free Edition**; do not
  assume the export exists.
- Validation: `sql/validation/06_dashboard_reconciliation.sql` and `docs/evidence/d3-03-dashboard-reconciliation.md` (D3-03, REQ-16).
