# D3-01 / D3-02 AI/BI dashboard (owner-reported)

> Built by the owner on 2026-10-10 in the Databricks AI/BI dashboard editor (Free Edition, serverless) from `dashboards/DASHBOARD_SPEC.md`.
> Facts below are owner-reported, plus what the coding agent could check in the 10 screenshots and the exported definition. The agent has no
> Databricks access.

## Dashboard

| Item | Value |
| ---- | ----- |
| Name | "Indonesian Bank Stocks - Performance and Risk" |
| Pages | 1 ("Performance and Risk") |
| Datasets (rows) | `ds_summary` 4 · `ds_daily` 7,544 · `ds_monthly` 376 · `ds_yearly` 32 |
| Dataset SQL | Unchanged from `dashboards/datasets/*.sql`. Agent check: the SQL in the export equals the four repo files (comments and whitespace ignored). |
| Custom calculations | None (all Transform = None). Agent check: every field expression in the export is a plain column reference, except the query generated automatically for the ticker filter widget. |
| Publishing | Published with individual data permissions; not shared |
| Export | `.lvdash.json` via **⋮ → File actions → Export** (held locally; see "Export file" below) |

## Visuals as built

| ID | Title | Type | Notes |
| -- | ----- | ---- | ----- |
| V1 | Full-period summary | Table | Spec columns plus `source_run_id` |
| V2 | Total return since 2019-01-02 | Bar | `total_return` by bank |
| V3 | Normalized price index (base 100 = 2019-01-02) | Line | Subtitle: "Base 100 = 2019-01-02; not rebased to the filter start." |
| V4 | Rolling volatility (60 sessions, annualized) | Line | Subtitle about the 60-session warm-up and the gaps (see note) |
| V5 | Full-period volatility (annualized) | Bar | `vol_full_ann` by bank |
| V6 | Drawdown from running peak | Line | Subtitle: decline from the running peak since 2019-01-02, not reset to the filter start, values ≤ 0 (see note) |
| V7 | Calendar-year return | Grouped bar | `yearly_return` by `year_label`; labels rotated 90° so "2026 (partial)" stays visible |
| V8 | Monthly return | Pivot | Rows `month_start`, `is_partial`; columns `ticker`; totals off |
| V9 | Average daily volume per month | Line | Caption: "Compare each bank with itself over time, not levels across banks (share counts differ)." |

**Fixed ticker colours** (V3, V4, V6, V7, V9): BBCA `#8BCAE7`, BBNI `#FFAB00`, BBRI `#00A972`, BMRI `#FF3621`. In the export these are fixed
per-ticker mappings to theme palette positions.

**Final subtitles** (in the exported definition and in the retaken screenshots):
- V4: "Gaps = zero-volume days (holidays, vendor gaps) excluded from return statistics."
- V6: "Decline from the running peak since 2019-01-02; not reset to the filter start. Values are ≤ 0."

*History:* the first set of screenshots (taken before the final edits) showed the earlier V4 subtitle ("First 60 sessions are empty by definition."),
the earlier V6 subtitle ("Decline from the running peak; values are ≤ 0.") and a cut-off "2026 (partial)" label. They were replaced on 2026-10-10 after the
clean-state run (`docs/evidence/d3-04-clean-state.md`).

## Filters (page level)

| Filter | Type | Applies to | Description shown |
| ------ | ---- | ---------- | ----------------- |
| Ticker | Multi-select | All 4 datasets (tested with BBCA and BBNI; the screenshots show BBCA) | — |
| Trade date | Date range on `ds_daily.trade_date` | V3, V4, V6 only | Full-period KPIs (V1, V2, V5) and calendar-year returns (V7) do not change with this filter |
| Month | Date range on `ds_monthly.month_start` | V8, V9 only | Same statement, plus "Filters on month_start (first day of each month)" |

Cross-filtering is left at the default (on for table, pivot and bar).

## Cross-checks (owner-reported)

- V3 = 100.00 for all four tickers on 2019-01-02.
- V6 BBNI on 2020-03-24 = −66.16%, which equals the V1 max drawdown for BNI.
- The V2 and V5 tooltips match V1.
- The full reconciliation against independent Silver queries is in `docs/evidence/d3-03-dashboard-reconciliation.md`.

## Screenshots

All 10 (retaken 2026-10-10) were checked by the coding agent: none shows an email address, account name, workspace host or URL.

| File | View |
| ---- | ---- |
| [`01-unfiltered-overview.png`](dashboard/01-unfiltered-overview.png) | Whole page, no filter |
| [`02-unfiltered-header-filters-v1.png`](dashboard/02-unfiltered-header-filters-v1.png) | Header, filters, V1 |
| [`03-unfiltered-v2-v5-v3.png`](dashboard/03-unfiltered-v2-v5-v3.png) | V2, V5, V3 |
| [`04-unfiltered-v4-v6-v7-v8.png`](dashboard/04-unfiltered-v4-v6-v7-v8.png) | V4, V6, V7, V8 |
| [`05-unfiltered-v9-footer.png`](dashboard/05-unfiltered-v9-footer.png) | V9, footer definitions |
| [`06-bbca-overview.png`](dashboard/06-bbca-overview.png) | Whole page, ticker = BBCA |
| [`07-bbca-header-filters-v1.png`](dashboard/07-bbca-header-filters-v1.png) | Header, filters, V1 (BBCA) |
| [`08-bbca-v2-v5-v3.png`](dashboard/08-bbca-v2-v5-v3.png) | V2, V5, V3 with tooltip 2021-12-03: 147.92 (BBCA) |
| [`09-bbca-v4-v6-v7-v8.png`](dashboard/09-bbca-v4-v6-v7-v8.png) | V4, V6, V7, V8 (BBCA) |
| [`10-bbca-v9-footer.png`](dashboard/10-bbca-v9-footer.png) | V9, footer (BBCA) |

The screenshots are stored in `docs/evidence/dashboard/` and were **retaken after the clean-state run** (`docs/evidence/d3-04-clean-state.md`). They
show the final version of the dashboard: the final V4/V6 subtitles and a fully visible "2026 (partial)" label. The agent re-inspected all 10: no
account information is visible.

## Export file

`dashboards/indonesian_bank_stocks.lvdash.json` was scanned by the agent. It contains no email, user path, host, URL or token. It does contain Databricks
object IDs: the dashboard ID and four dataset IDs inside the filter widgets' query names. They are not secrets, but they identify objects in the
owner's workspace. **Owner decision 2026-10-10 (DEC-16): committed as is**, unedited. The IDs are not credentials; whether an import assigns new IDs is
unverified.
