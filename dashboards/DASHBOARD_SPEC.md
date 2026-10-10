# Dashboard specification: "Indonesian Bank Stocks - Performance and Risk"

> Build guide for the Databricks **AI/BI dashboard** (one page, "Performance and Risk") on the Gold layer. It is updated to match the dashboard as
> built on 2026-10-10 (`docs/evidence/d3-01-dashboard.md`). KPI definitions: `docs/KPI_DEFINITIONS.md`. Data model: `docs/DATA_MODEL.md` §4.
> The datasets are thin `SELECT`s over Gold in `dashboards/datasets/`; no KPI is computed in the dashboard (no custom calculations, Transform = None).
> Menu names are those observed in the Databricks Free Edition editor on 2026-10-10.

## 1. Datasets (Data tab → "Create from SQL")

Create one dataset per file and paste the file's SQL as is.

| Dataset | File | Grain | Rows (2026-10-08 snapshot) | Used by |
| ------- | ---- | ----- | -------------------------: | ------- |
| `ds_summary` | `dashboards/datasets/ds_summary.sql` | ticker | 4 | V1, V2, V5 |
| `ds_daily` | `dashboards/datasets/ds_daily.sql` | ticker × trade_date | 7,544 | V3, V4, V6 |
| `ds_monthly` | `dashboards/datasets/ds_monthly.sql` | ticker × month_start | 376 | V8, V9 |
| `ds_yearly` | `dashboards/datasets/ds_yearly.sql` | ticker × year | 32 | V7 |

## 2. Header text widget

Add a text widget; edit its content with **Edit markdown** and preview it with **Show rich text**.

```markdown
# Indonesian Bank Stocks - Performance and Risk
Descriptive comparison of BBCA, BBNI, BMRI and BBRI since 2019 - not investment advice.
**Data snapshot:** see `last_trade_date` and `source_run_id` in the summary table.
**Definitions:** total return uses `adjclose` (adjusted for dividends and corporate actions) · volatility = 60-session rolling standard deviation
of daily returns × √252 · drawdown = decline from the running peak · partial periods are flagged · zero-volume rows are excluded from return statistics.
```

## 3. Filters (page level)

| Filter | Type | Field(s) | Applies to | Description text |
| ------ | ---- | -------- | ---------- | ---------------- |
| Ticker | Multi-select | `ticker` in all 4 datasets | All visuals | — |
| Trade date | Date range | `ds_daily.trade_date` | V3, V4, V6 only | "Applies to V3, V4, V6 only. Full-period KPIs (V1, V2, V5) and calendar-year returns (V7) do not change with this filter." |
| Month | Date range | `ds_monthly.month_start` | V8, V9 only | "Applies to V8, V9 only. Filters on month_start (first day of each month). Full-period KPIs (V1, V2, V5) and calendar-year returns (V7) do not change with this filter." |

- The summary KPIs (V1, V2, V5) and the yearly returns (V7) are **full-period / fixed-period values**; they do **not** change with the date filters.
  Window KPIs (over an arbitrary date range) would need the SHOULD table function `gold.fn_window_performance`, which is not in v1.
- **Cross-filtering** is left at the default (on for the table, pivot and bar visuals).

## 4. Visuals

**Formatting.** Every return, volatility and drawdown field uses **Format → Custom → Type "%"**, with **Decimal places: Exact, 2**.
`normalized_index` is a number with 2 decimals. Volumes use **Number abbreviation: None** (other options: Compact, Scientific).
Dates use `YYYY-MM-DD`.

**Fixed ticker colours** (V3, V4, V6, V7, V9): BBCA `#8BCAE7`, BBNI `#FFAB00`, BBRI `#00A972`, BMRI `#FF3621`.

| ID | Title | Dataset | Type | X | Y | Color / series | Subtitle, formatting, notes | Question |
| -- | ----- | ------- | ---- | - | - | -------------- | --------------------------- | -------- |
| V1 | Full-period summary | `ds_summary` | Table | — | Columns: `short_name`, `total_return`, `vol_full_ann`, `max_drawdown`, `peak_date`, `trough_date`, `current_drawdown`, `last_trade_date`, `source_run_id` | — | Headers: Bank, Total return, Volatility (ann.), Max drawdown, Peak date, Trough date, Current drawdown, Last trade date, Source run ID | Q1–Q3 |
| V2 | Total return since 2019-01-02 | `ds_summary` | Bar | `short_name` | `total_return` | — | Sorted descending | Q1 |
| V3 | Normalized price index (base 100 = 2019-01-02) | `ds_daily` | Line | `trade_date` | `normalized_index` | `ticker` | Subtitle: "Base 100 = 2019-01-02; not rebased to the filter start." | Q1 |
| V4 | Rolling volatility (60 sessions, annualized) | `ds_daily` | Line | `trade_date` | `vol_60d_ann` | `ticker` | Subtitle: "Gaps = zero-volume days (holidays, vendor gaps) excluded from return statistics." The first 60 sessions are empty by definition. | Q2 |
| V5 | Full-period volatility (annualized) | `ds_summary` | Bar | `short_name` | `vol_full_ann` | — | Sorted descending | Q2 |
| V6 | Drawdown from running peak | `ds_daily` | Line | `trade_date` | `drawdown` | `ticker` | Subtitle: "Decline from the running peak since 2019-01-02; not reset to the filter start. Values are ≤ 0." | Q3 |
| V7 | Calendar-year return | `ds_yearly` | Grouped bar | `year_label` | `yearly_return` | `ticker` | Grouping is set under **Y axis → Layout**. X labels rotated 90° so "2026 (partial)" stays visible; check that the panel is tall enough. | Q4 |
| V8 | Monthly return | `ds_monthly` | Pivot | Rows: `month_start`, `is_partial` | Cells: `monthly_return` | Columns: `ticker` | Totals off | Q4 |
| V9 | Average daily volume per month | `ds_monthly` | Line | `month_start` | `avg_daily_volume` | `ticker` | Subtitle: "Compare each bank with itself over time, not levels across banks (share counts differ)." | Q5 (SHOULD) |

## 5. Layout (rows from top to bottom)

1. Header text widget (full width).
2. Filters: Ticker | Trade date | Month.
3. V1 summary table (full width).
4. V2 total return (half) | V5 full-period volatility (half).
5. V3 normalized index (full width).
6. V4 rolling volatility (half) | V6 drawdown (half).
7. V7 calendar-year return (half) | V8 monthly return (half).
8. V9 average daily volume (full width).
9. Footer text widget: metric definitions.

Footer text widget:

```markdown
**Metric definitions** (full text: docs/KPI_DEFINITIONS.md in the project repository)
- Total return (K2) = last adjclose / adjclose on the base date (2019-01-02) - 1.
- Volatility (K4/K5) = sample standard deviation of daily returns on normal (traded) sessions × √252; K4 uses the last 60 sessions.
- Drawdown (K6) = adjclose / running peak - 1; max drawdown (K7) is its minimum; peak date = the day the peak was set.
- Monthly / yearly return (K8/K9) = period-end adjclose / previous period-end adjclose - 1; the first period starts at the base date.
- Partial = first period, or the period still running at the snapshot's last trade date.
```

## 6. Publish, export, re-create

- **Publish** with individual data permissions (each viewer uses their own access); the dashboard was not shared.
- **Export** the definition: **⋮ → File actions → Export** produces a `.lvdash.json` file. The committed export
  `dashboards/indonesian_bank_stocks.lvdash.json` contains Databricks object IDs (dashboard and dataset IDs) from the original workspace; they are not
  credentials, and whether an import assigns new IDs is unverified.
- **Re-create from an export** *(to be verified)*: AI/BI dashboards can be imported from a `.lvdash.json` file through the dashboards list
  (an "Import dashboard from file" option is expected in the Create menu). Afterwards, check that each dataset points to your catalog, then publish.
  If import is not available, rebuild from this guide; the dataset SQL files make that a copy-paste exercise.
- After a pipeline run, refresh the dashboard. The values must match `docs/evidence/d3-03-dashboard-reconciliation.md` when the data snapshot is unchanged.
- Screenshots live in `docs/evidence/dashboard/` (`01-…png` to `10-…png`); retaken after the clean-state run, they show the final version
  (`docs/evidence/d3-04-clean-state.md`).
