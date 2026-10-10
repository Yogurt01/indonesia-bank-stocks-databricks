# D2-05 Gold build (owner-reported)

> Run by the owner on 2026-10-10 between about 00:23 and 00:27 (UTC+07): notebook `notebooks/03_gold_build` run **twice** interactively from the
> Databricks Git folder on serverless compute. Validation queries: [`sql/validation/03_gold.sql`](../../sql/validation/03_gold.sql).
> Results are owner-reported; the coding agent has no Databricks access and has not independently verified them.

## Notebook output and audit

Both runs ended with **GOLD PASS**. `ops.run_audit` holds 2 `SUCCEEDED` rows for `gold_build`: `rows_in = 7548`, `rows_out = 7544`, `rows_rejected = 0`.

## Row counts and keys (G1/G2)

| Table | Rows | Distinct keys |
| ----- | ---: | ------------: |
| `gold.dim_ticker` | 4 | 4 |
| `gold.fact_daily_metrics` | 7,544 | 7,544 |
| `gold.fact_monthly_metrics` | 376 | 376 |
| `gold.fact_yearly_metrics` | 32 | 32 |
| `gold.ticker_summary` | 4 | 4 |

## Gold checks (G7)

10/10 passed:
- `gold_daily_rows_match_silver`: gold = 7544, silver = 7544, base_date = 2019-01-02.
- `gold_vol_leading_nulls`: 60 per ticker.
- `gold_partial_periods` (INFO): `failing_count = 16` (2 partial months and 2 partial years per ticker).

## Reconciliation seed (G6)

An independent recomputation of `total_return` from `silver.daily_prices` (last `adjclose` / `adjclose` on 2019-01-02 − 1), compared with
`gold.ticker_summary.total_return`: **`abs_diff = 0` for all four tickers.**

## ticker_summary (G3)

base_date 2019-01-02, last_trade_date 2026-10-08. Values ending in "…" were truncated in the screenshot.

| ticker | total_return | vol_full_ann | max_drawdown | peak_date | trough_date | current_drawdown |
| ------ | -----------: | -----------: | -----------: | --------- | ----------- | ---------------: |
| BBCA | 0.4096571841753591 | 0.2622313492568432 | -0.5179204835090025 | 2024-09-23 | 2026-06-08 | -0.39938712852597347 |
| BBNI | 0.0949590457301969… | 0.3414590613143148 | -0.6615630803271564 | 2019-04-19 ¹ | 2020-03-24 | -0.32155547334748835 |
| BBRI | 0.4301591927421744 | 0.326187784017586… | -0.5243351988752678 | 2020-01-24 | 2020-05-18 | -0.41918132556542265 |
| BMRI | 0.7596948888403188 | 0.3350570398009743 | -0.5205072369380116 | 2019-07-15 | 2020-05-18 | -0.3335650778338555 |

¹ **Produced by the earlier K7 rule** (latest date ≤ trough with `drawdown = 0`). 2019-04-19 is a `zero_all_tickers` flat row (a non-trading day,
`docs/DATASET.md` §6.3). The rule was changed on 2026-10-10 (**DEC-14**: `peak_date` = the day the peak was set). The value is kept here as recorded;
the DEC-14 rebuild reports 2019-04-18 (see "DEC-14 rebuild" below, which also lists the BBRI change).

## Yearly returns captured (G4)

Only the rows visible in the owner's screenshot are recorded. The remaining BBRI rows and all BMRI rows were **not captured**.

| ticker | year | yearly_return | n_sessions | is_partial |
| ------ | ---: | ------------: | ---------: | ---------- |
| BBCA | 2019 | 0.29149985207088713 | 257 | true |
| BBCA | 2020 | 0.03334280509869369 | 242 | false |
| BBCA | 2021 | 0.09707080349287556 | 247 | false |
| BBCA | 2022 | 0.19382545548113872 | 246 | false |
| BBCA | 2023 | 0.12674107888839248 | 239 | false |
| BBCA | 2024 | 0.058224914084562984 | 237 | false |
| BBCA | 2025 | -0.1340066701029271 | 236 | false |
| BBCA | 2026 | -0.21894326990722157 | 182 | true |
| BBNI | 2019 | -0.0787233076804219 | 257 | true |
| BBNI | 2020 | -0.18958338332542823 | 242 | false |
| BBNI | 2021 | 0.10151407495731002 | 247 | false |
| BBNI | 2022 | 0.39188382941823496 | 246 | false |
| BBNI | 2023 | 0.21556972468764402 | 239 | false |
| BBNI | 2024 | -0.15202223513270863 | 237 | false |
| BBNI | 2025 | 0.09458384123725638 | 236 | false |
| BBNI | 2026 | -0.15220072203419477 | 182 | true |
| BBRI | 2019 | 0.26216796529972264 | 257 | true |

## Sanity notes (observations)

- **Yearly returns compound to total return** (checked by the coding agent from the reported numbers): the product of (1 + yearly_return) over
  2019–2026, minus 1, equals the reported `total_return` within 3e-16 for BBCA and BBNI. (BBNI's `total_return` was truncated in the screenshot.)
- **Total returns** are within about 2 percentage points of the illustrative DEC-03 estimates in `docs/KPI_DEFINITIONS.md` §5: BBCA −1.0, BBNI +0.9,
  BBRI +2.0, BMRI +1.0. The difference comes from the base date (2019-01-02 instead of 2019-01-01).
- **Peak and trough dates:** BBCA's `peak_date` (2024-09-23) and the BBNI, BBRI and BMRI `trough_date`s (2020-03-24, 2020-05-18, 2020-05-18) equal the
  `close` max/min dates in `docs/DATASET.md` §5.
- **BBCA's deepest drawdown** is the 2024-09 → 2026-06 episode, not 2020.
- **`n_sessions`** of 257 (2019, counted from the base date) and 242 (2020) match the local profile (258 rows in 2019 minus 2019-01-01; 242 in 2020).

## Not verified by this evidence

- Gold built by a Job run (see `docs/evidence/d2-06-job.md`).
- The rerun idempotency comparison (D2-07) and the dashboard reconciliation (REQ-16).

## DEC-14 rebuild (owner-reported, 2026-10-10 about 11:50–12:02 UTC+07)

Job run **766912259782044** rebuilt Gold with the DEC-14 `peak_date` rule (the day the peak was set).

- **G6:** `abs_diff = 0` for all four tickers, so `total_return` is unchanged.
- **G9** (`sql/validation/03_gold.sql`): every `peak_date` row is a normal trading day, and `peak_adjclose` equals `running_peak_at_trough`.

| ticker | peak_date | trough_date | peak volume_status | peak_adjclose = running_peak_at_trough |
| ------ | --------- | ----------- | ------------------ | -------------------------------------: |
| BBCA | 2024-09-23 | 2026-06-08 | normal | 9989.7958984375 |
| BBNI | 2019-04-18 | 2020-03-24 | normal | 3515.825439453125 |
| BBRI | 2020-01-23 | 2020-05-18 | normal | 2880.720458984375 |
| BMRI | 2019-07-15 | 2020-05-18 | normal | 2610.930419921875 |

**Changes compared with the old rule** (the ticker_summary table above):
- **BBNI:** 2019-04-19 → **2019-04-18**. The old date was a `zero_all_tickers` flat row.
- **BBRI:** 2020-01-24 → **2020-01-23**. Two consecutive sessions closed at the same `adjclose`; the new rule reports the first one, the date the
  peak was set.
- **BBCA and BMRI:** unchanged.

`notebooks/91_rerun_check` was **not** rerun for this build, because DEC-14 intentionally changed `peak_date`. The rerun evidence in
`docs/evidence/d2-07-rerun.md` stands.
