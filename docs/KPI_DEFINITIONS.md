# KPI Definitions: Indonesian Banking Stock Performance Analytics

> **Status: owner-approved 2026-10-09 (DEC-03); implementation pending.** These are design decisions, not measured results.
> Every "expected" value below is a prediction to be verified on Databricks (§7). Facts about the source data come from
> [`docs/DATASET.md`](DATASET.md), which records what was actually verified.

## 1. Purpose and Audience

A descriptive, historical comparison of **BBCA, BBNI, BMRI and BBRI** for an **individual investment analyst**.
It is **not investment advice** and makes **no forecasts**. The data contains only prices and volume: no fundamentals and no shares outstanding,
so there is no market capitalization, valuation or turnover ratio.

## 2. Business Questions

| ID | Priority | Question |
| -- | -------- | -------- |
| Q1 | MUST | Over a chosen period, which stock delivered the highest total return, and how did the comparative performance path evolve? |
| Q2 | MUST | Which stock is most volatile, and how did volatility change over time (especially in 2020)? |
| Q3 | MUST | What was each stock's deepest decline from a peak, and how far is it currently below its peak? |
| Q4 | MUST | How do monthly and yearly returns compare across the four stocks? |
| Q5 | SHOULD | How does trading volume change over time relative to each stock's own normal level? |

## 3. Global Rules

- **G1 Price basis.**
  - `adjclose` is used for all performance, return, volatility and drawdown metrics. This is *total return*: adjusted for corporate actions and dividends, both **inferred** per `DATASET.md` §6.5.
  - `close` is kept in Silver and Gold as a reference price only. Price return is not a v1 KPI.
  - **Terminology:** "price return" means `close`-based; "total return" means `adjclose`-based.
  - The dataset has **no as-traded price**.
  - `adjclose` levels are rewritten on every full refresh, so `adjclose` is used **for ratios only** and is never displayed as a price level.
- **G2 Return type.** Simple returns: `r(t) = adjclose(t) / adjclose(prev) − 1`. Period return = `adjclose(end) / adjclose(start) − 1`.
  Log returns were rejected: they are harder to read and do not map directly onto the normalized index.
- **G3 Base date.** The earliest `trade_date` on which **all four tickers have `volume > 0`**. This is expected to be 2019-01-02 and **must be verified by a
  Silver query, not hard-coded**. 2019-01-01 is a zero-volume flat row in all four tickers (`DATASET.md` §6.3). Gold series start at the base date.
- **G4 `volume_status` (a Silver column, derived by rule with no hard-coded dates):**
  - `normal`: `volume > 0`;
  - `zero_all_tickers`: `volume = 0` for this ticker **and** for all four tickers on that date;
  - `zero_partial`: `volume = 0` for this ticker while at least one other ticker has `volume > 0` on that date.

  The names describe the observation; "exchange holiday" and "vendor gap" are interpretations **(inferred)**.
  **No row is deleted or quarantined for zero volume.**
- **G5 Rows used.** Return statistics (K3, K4, K5, K10) use **`normal` rows only**; flagged rows get **NULL** returns, not 0%.
  Levels and period returns (K1, K2, K6–K9) use **all rows**. Flat rows carry the previous price, so they do not distort them.
- **G6 Snapshot lineage.** Every Gold table carries the snapshot lineage, because `adjclose` changes on every refresh: the source `run_id`
  (from `run-summary.json`), `source_ingested_at` = `max(ingested_at_utc)` from the daily CSVs, and the pipeline run ID. Kaggle `lastUpdated` is **not** in the files
  landed in Databricks (it comes from the Kaggle CLI), so it is recorded in documentation at download time only.
- **G7 Parameters live in configuration, not code:** `vol_window = 60`, `rel_volume_window = 60`, `annualization_factor = 252`.

## 4. KPI Table

| ID | KPI | Formula | Grain | Rows used | Question | Priority |
| -- | --- | ------- | ----- | --------- | -------- | -------- |
| K1 | Normalized index | `100 * adjclose(t) / adjclose(base_date)` | ticker × day | all rows from base date | Q1 | MUST |
| K2 | Full-period total return | `adjclose(last date) / adjclose(base_date) - 1` | ticker | all rows | Q1 | MUST |
| K3 | Daily return | `adjclose(t) / adjclose(previous normal row) - 1`; NULL on flagged rows | ticker × day | normal only | Q2 | MUST |
| K4 | Rolling volatility | `stddev_samp(K3 over the last 60 normal rows including t) * sqrt(252)`; NULL until 60 observations | ticker × day | normal only | Q2 | MUST |
| K5 | Full-period volatility | `stddev_samp(all K3) * sqrt(252)` | ticker | normal only | Q2 | MUST |
| K6 | Drawdown | `adjclose(t) / max(adjclose from base_date to t) - 1` (always ≤ 0); also store `running_peak` | ticker × day | all rows | Q3 | MUST |
| K7 | Max and current drawdown | `max_drawdown = min(K6)`; `peak_date` and `trough_date` of that episode; `current_drawdown` = K6 on the last date | ticker | all rows | Q3 | MUST |
| K8 | Monthly return | `adjclose(last row of month m) / adjclose(last row of month m-1) - 1`; the first period starts at `base_date`; `is_partial` flag | ticker × month | all rows | Q4 | MUST |
| K9 | Yearly return | Same as K8 by calendar year; `is_partial` flag | ticker × year | all rows | Q4 | MUST |
| K10 | Relative volume | `volume(t) / avg(volume over the 60 previous normal rows, excluding t)`; NULL until 60 are available | ticker × day | normal only | Q5 | SHOULD |
| K11 | Average daily volume per month | `avg(volume)` over normal rows in the month | ticker × month | normal only | Q5 | SHOULD |

**`is_partial` (K8, K9)** is TRUE for the first period (which starts at `base_date`) and for any period not complete at the snapshot's last date.
In the current snapshot that means October 2026 and the year 2026. It is derived from the data, not hard-coded.

**Source columns:** `trade_date`, `ticker`, `adjclose` (K1–K9), `volume` (K10, K11, and `volume_status` for all), plus the G6 lineage columns.

## 5. Rationale

- **`adjclose`** gives a fair comparison across banks with different dividend policies, and volatility is not inflated by ex-dividend drops.
- **Why the basis matters, illustrated.** This is an **ESTIMATE, not a measured result.** It is derived from the first and last `close` values and the minimum `adjclose/close` ratio in `DATASET.md` §5, assuming the minimum falls on the first date. Full-period price return vs total return:

  | Ticker | Price return | Total return |
  | ------ | -----------: | -----------: |
  | BBCA | +15.4% | ~+42% |
  | BBNI | −22.5% | ~+8.6% |
  | BBRI | −8.9% | ~+41% |
  | BMRI | +8.5% | ~+75% |

  The ranking changes with the basis. The real values come from K2 after implementation.
  The "minimum ratio on the first date" assumption was confirmed by Bronze query Q3 ([`docs/evidence/d2-01-bronze.md`](evidence/d2-01-bronze.md)): the 2019-01-01 `adjclose/close` ratios equal the §5 minimums. The full-period figures remain estimates until Gold computes K2 from the base date.
- **Window 60** is smoother than 20 and still shows March 2020.
- **`sqrt(252)`** is a convention. The observed ~236–247 normal sessions per year make annualized values ~2–3% higher. The same factor is used for every ticker, so rankings are unaffected. Label it on the dashboard.
- **Drawdown uses close-based `adjclose`, not the intraday low,** because `low` is not dividend-adjusted.
- **K10 uses the average, not the median,** because a rolling median on serverless is unverified.

## 6. Known Limitations

- There are no as-traded prices. The adjustment methodology is the vendor's **(inferred)**.
- `adjclose` is rewritten on every refresh, so KPI history belongs to a snapshot (G6).
- The 252-session annualization is a convention, not the observed session count.
- K10 is sensitive to volume spikes because it uses the mean.
- Volume may not be adjusted for corporate actions (see risk R-16 in `PROJECT_PLAN.md`).
- KPIs over an arbitrary dashboard date window (rebased index, window volatility, window drawdown) are **not precomputed in v1**. This is a design point for DEC-08.

## 7. To Verify on Databricks

| Check | Expected (from `DATASET.md` facts, not yet verified on Databricks) |
| ----- | ------------------------------------------------------------------ |
| Base date value (G3) | 2019-01-02. **Verified 2026-10-10** ([`docs/evidence/d2-03-silver.md`](evidence/d2-03-silver.md)) |
| `volume_status` counts | 52 `zero_all_tickers` (13 dates × 4); 4 `zero_partial` (2020-03-13: BBCA, BBNI; 2020-03-16: BBCA, BMRI). **Verified 2026-10-10** ([`docs/evidence/d2-03-silver.md`](evidence/d2-03-silver.md)) |
| Every zero-volume row is flat (open = high = low = close = previous close) | 0 exceptions. **Verified 2026-10-10** ([`docs/evidence/d2-03-silver.md`](evidence/d2-03-silver.md)) |
| `adjclose` on flat rows equals the previous row's `adjclose` | 0 exceptions. **Verified 2026-10-10** ([`docs/evidence/d2-03-silver.md`](evidence/d2-03-silver.md)) |
| Normal sessions per year | ~236–247 |
| K4 leading NULLs per ticker | Exactly 60 (K3 is NULL on the base date because there is no earlier normal row, so 60 K3 observations first exist on the 61st normal row) |
| K6 | Never positive; 0 on new peaks |
| K7 | `trough_date` after `peak_date` |
| K8 vs K9 consistency | Product of (1 + K8) within a year equals 1 + K9, within rounding tolerance |
| `is_partial` counts | First month and year, plus October 2026 and 2026 in the current snapshot |
| Volume level shift around the adjustment dates | BBNI ~2023-10-05, BMRI ~2023-04-03 (R-16) |
## 8. Implied Data Quality Rules (to be cataloged in D1-09)

| Rule | Severity | Expected |
| ---- | -------- | -------- |
| Zero-volume row whose prices are not flat | WARN | 0 |
| `zero_partial` rows (count persisted per run) | WARN | 4 in the current snapshot |
| `zero_all_tickers` rows | INFO | 52 in the current snapshot |

## 9. Deferred (COULD)

- Recovery time after a drawdown.
- 20-session volatility.
- Window-specific KPIs (over an arbitrary dashboard date range).
- Reconciliation against the source weekly and monthly files.
