# Dataset Collection: Indonesian Banking Stock Prices (BBCA, BBNI, BMRI, BBRI)

> Everything below comes from the files actually downloaded and inspected read-only on **2026-10-09**: BBCA at about 17:20,
> and BBNI, BMRI and BBRI at about 20:20, Asia/Ho_Chi_Minh (UTC+07). Items marked **(inferred)** or **(unverified)** were
> not confirmed from the files or the source metadata. All figures describe this snapshot only. A later download can differ (see §6).

## 1. Dataset Collection Overview

**Project purpose:** source data for the Databricks Bronze → Silver → Gold batch pipeline described in `README.md` and `docs/ARCHITECTURE.md`.
**Business domain (owner-approved, DEC-02):** Financial Market Analytics, specifically Indonesian Banking Stock Performance Analytics:
comparing the historical price performance, returns, volatility and trading volume of four Indonesian banks.

| Ticker | Bank | Kaggle dataset (slug) | Kaggle ID | URL |
| ------ | ---- | --------------------- | --------: | --- |
| BBCA.JK | PT Bank Central Asia Tbk | `caesarmario/bank-central-asia-stock-historical-price` | 4259980 | <https://www.kaggle.com/datasets/caesarmario/bank-central-asia-stock-historical-price> |
| BBNI.JK | PT Bank Negara Indonesia (Persero) Tbk | `caesarmario/bank-negara-indonesia-stock-historical-price` | 4260212 | <https://www.kaggle.com/datasets/caesarmario/bank-negara-indonesia-stock-historical-price> |
| BMRI.JK | PT Bank Mandiri (Persero) Tbk | `caesarmario/bank-mandiri-stock-historical-price` | 4260117 | <https://www.kaggle.com/datasets/caesarmario/bank-mandiri-stock-historical-price> |
| BBRI.JK | PT Bank Rakyat Indonesia (Persero) Tbk | `caesarmario/bank-rakyat-indonesia-stock-historical-price` | 4255694 | <https://www.kaggle.com/datasets/caesarmario/bank-rakyat-indonesia-stock-historical-price> |

All four slugs were confirmed in the uploader's dataset listing (`kaggle datasets list --user caesarmario`) and in each dataset's metadata (`ownerUser: caesarmario`).
The Kaggle subtitles all read "<TICKER> Stock Price from January 2019 - Present".

**Publication time vs trading-date coverage.** These are different things:

| Item | BBCA | BBNI | BMRI | BBRI |
| ---- | ---- | ---- | ---- | ---- |
| Kaggle `lastUpdated` (UTC, publish time) | 2026-10-09 05:45:50 | 2026-10-09 05:46:19 | 2026-10-09 05:46:04 | 2026-10-09 05:45:34 |
| Source `run_id` (`run-summary.json`) | `20261009T124332+0700` | same | same | same |
| `ingested_at_utc` (daily file; the uploader's write time) | 05:43:40.88 | 05:43:45.99 | 05:43:43.38 | 05:43:38.29 |
| **Actual daily trading dates** | **2019-01-01 → 2026-10-08** | same | same | same |

All four share one `run_id`, so one upstream job produces every dataset **(inferred)**. 2026-10-09 is in no record.

## 2. Source and Provenance

- **Upstream source (as the uploader states it):** Yahoo Finance (`userSpecifiedSources` points to `finance.yahoo.com/quote/<TICKER>`). Every `run-metadata*.json` gives `"source": "yahoo_fin"` (a Python library that reads Yahoo Finance) and `"mode": "full"` (the history from 2019-01-01 is re-extracted on every run). `expectedUpdateFrequency` is `daily`.
- **Uploader log (BBCA description; the other descriptions were not compared word for word):** automated updates since 2024-01-04. Since 2026-01-13 it has been a "production-style ETL (idempotent outputs + basic DQ + run metadata)" that also emits Parquet and the run-summary file.
- **License metadata (verified):** the Kaggle license field is `world-bank` for **all four** datasets (`dataset-metadata.json`, and the CLI's "License(s): world-bank" output).
- **Unresolved upstream terms:**
  - Yahoo Finance's terms for redistributing its price data were **not verified**.
  - A World Bank license label on Yahoo-derived data is unusual, and Kaggle hosting it publicly **does not prove** that unrestricted redistribution is allowed.
  - This document makes no legal determination. See §10 for how the public repository handles this.
- **Not verifiable:** the uploader's notebook code; the vendor's corporate-action methodology; whether earlier Kaggle versions had different values (no version history inspected).

## 3. Dataset Inventory

| Ticker | Bank | Local directory | Files (formats) | Downloaded bytes | Archive (bytes; SHA-256 prefix) | Daily / weekly / monthly rows | Daily dates | Verification |
| ------ | ---- | --------------- | --------------- | ---------------: | ------------------------------- | ----------------------------- | ----------- | ------------ |
| BBCA.JK | Bank Central Asia | `data/raw/bbca/` | 10: 3 CSV, 3 Parquet, 4 JSON | 324,537 | 112,451; `fad9e1240d42` | 1,887 / 406 / 94 | 2019-01-01 → 2026-10-08 | ✅ Verified (see note) |
| BBNI.JK | Bank Negara Indonesia | `data/raw/bbni/` | 10: 3 CSV, 3 Parquet, 4 JSON | 323,887 | 111,640; `dcde9048a559` | 1,887 / 406 / 94 | 2019-01-01 → 2026-10-08 | ✅ Verified (see note) |
| BMRI.JK | Bank Mandiri | `data/raw/bmri/` | 10: 3 CSV, 3 Parquet, 4 JSON | 324,661 | 110,803; `a7919f23ee44` | 1,887 / 406 / 94 | 2019-01-01 → 2026-10-08 | ✅ Verified (see note) |
| BBRI.JK | Bank Rakyat Indonesia | `data/raw/bbri/` | 10: 3 CSV, 3 Parquet, 4 JSON | 362,147 | 120,121; `fd2faee31304` | 1,887 / 406 / 94 | 2019-01-01 → 2026-10-08 | ✅ Verified (see note) |
| **Total** | | `data/raw/` | **40** | **1,335,232** | | | | |

**Verified** means all of the following were checked for that ticker:
- the file names and byte sizes match `kaggle datasets files`;
- `unzip -t` reported no errors;
- every extracted file is byte-identical to its archive member (BBNI, BMRI and BBRI);
- the SHA-256 checksums were unchanged after profiling.

The archives were not kept (to avoid storing the data twice). Their checksums are recorded above.

**Per-ticker file layout.** `<T>` is the ticker (BBCA, BBNI, BMRI or BBRI). Sizes are in bytes.

| File | Purpose | BBCA | BBNI | BMRI | BBRI |
| ---- | ------- | ---: | ---: | ---: | ---: |
| `<T>.JK.csv` | Daily OHLCV, **recommended primary input** | 183,435 | 183,790 | 185,250 | 211,637 |
| `<T>.JK.parquet` | Same data as the daily CSV | 60,001 | 58,845 | 58,140 | 60,885 |
| `<T>.JK_weekly.csv` / `.parquet` | Source weekly bars (reference only) | 39,790 / 20,363 | 39,892 / 20,347 | 40,168 / 20,103 | 45,672 / 21,348 |
| `<T>.JK_monthly.csv` / `.parquet` | Source monthly bars (reference only) | 9,352 / 9,518 | 9,358 / 9,577 | 9,396 / 9,510 | 10,672 / 9,855 |
| `run-metadata.json`, `_weekly`, `_monthly` | The uploader's run parameters plus a `dq` summary per interval | 548 / 555 / 555 | 548 / 555 / 555 | 552 / 559 / 559 | 548 / 555 / 555 |
| `run-summary.json` | `stock`, `ticker`, `run_id`, and rows / `date_max` / `duplicate_dates` per interval | 420 | 420 | 424 | 420 |

BBRI's CSVs are larger because their prices carry up to 13 decimals (§4). The BMRI JSON files are 4 bytes larger because the
`stock` value is `mandiri` rather than a 3-letter code (`bca`, `bni`, `bri`).

**JSON contents (verified).** Each `run-metadata*.json` holds `interval` (`1d`/`1wk`/`1mo`), `source`, `mode`, `start_date_used`
(`01/01/2019`), `end_date_used` (`10/09/2026`, MM/DD/YYYY), `output_csv` (a path in the uploader's Kaggle environment, for example
`/kaggle/working/bri/BBRI.JK.csv`), `output_parquet`, and a `dq` block. **For all 12 metadata files, the `dq` row count, minimum and maximum date,
duplicate count, null count and negative-volume count match this profile exactly.**

## 4. Schema and Compatibility

All 24 price files (4 tickers × 3 intervals × 2 formats) have **the same 8 columns** with the same names, and every CSV has them in the same order.

| Column | CSV (inferred) | Parquet physical / logical type | Meaning | Normalization needed for Silver |
| ------ | -------------- | ------------------------------- | ------- | ------------------------------- |
| `Date` | `YYYY-MM-DD` | `INT64` / `TIMESTAMP(NANOS, isAdjustedToUTC=false)` | Bar label (trading day for daily data; see §6.1 for weekly and monthly) | Rename to `trade_date`; cast to `DATE` |
| `open`, `high`, `low`, `close` | float text | `DOUBLE` | Prices, corporate-action-adjusted **(inferred, §6.4)**; IDR **(inferred)** | Choose `DOUBLE` vs `DECIMAL(p,s)`; values carry float32 artifacts |
| `adjclose` | float text, up to 13 decimals | `DOUBLE` | Close also adjusted for dividends **(inferred)** | Same as the prices |
| `volume` | integer text | `INT64` | Bar volume; shares **(inferred)**, back-adjusted for corporate actions **(inferred)** | `BIGINT` |
| `ingested_at_utc` | `YYYY-MM-DD HH:MM:SS.ffffff+00:00` | `INT64` / `TIMESTAMP(MICROS, UTC)` | The uploader's write time (constant per file) | Keep as source lineage; it is not a market attribute |
| *(none)* | | | **No ticker column.** The ticker appears only in file names and `run-summary.json` | **Add `ticker` at ingestion** |

**Cross-dataset differences**
- **Price precision:** BBCA OHLC values are all whole numbers (`5200.0`).
  - BBNI and BMRI have `.5` values before their adjustment dates (899 and 875 daily rows respectively).
  - BBRI has non-tick values with up to 13 decimals before 2021-09-07 (666 daily rows, for example `3327.21533203125`).
  - Every OHLC and `adjclose` value in all four tickers is exactly representable as **float32**, so precision was reduced upstream and then written as double.
- **Parquet vs CSV (all 12 pairs):** equal row counts and **0 cell mismatches** across all 8 columns. The only differences are:
  - In Parquet, `Date` is the **last** column, because it was written from the pandas index (pandas 2.3.3, parquet-cpp-arrow 23.0.1, format 2.6, one row group).
  - `Date` is stored as a **nanosecond** timestamp. Whether Databricks/Spark reads that without configuration is **unverified** and must be tested in D1-04.

## 5. Coverage and Statistics (daily files)

| Metric | BBCA | BBNI | BMRI | BBRI |
| ------ | ---: | ---: | ---: | ---: |
| Rows | 1,887 | 1,887 | 1,887 | 1,887 |
| Date range | 2019-01-01 → 2026-10-08 | same | same | same |
| Empty / null cells | 0 | 0 | 0 | 0 |
| Duplicate rows / duplicate dates | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| OHLC violations, non-positive prices, negative volume | 0 | 0 | 0 | 0 |
| Zero-volume rows (all flat at the previous close) | 15 | 14 | 14 | 13 |
| `close`: first → last | 5,200 → 6,000 | 4,400 → 3,410 | 3,687.5 → 4,000 | 3,327.2153 → 3,030 |
| `close`: min (date) | 4,430 (2020-03-23) | 1,580 (2020-03-24) | 1,860 (2020-05-18) | 1,972.69 (2020-05-18) |
| `close`: max (date) | 10,950 (2024-09-23) | 6,225 (2024-03-13) | 7,450 (2024-09-23) | 6,400 (2024-03-13) |
| Largest daily close-to-close fall | −8.53% (2025-04-08) | −11.72% (2020-03-09) | −12.99% (2020-03-17) | −10.12% (2025-04-08) |
| Largest daily close-to-close rise | +17.33% (2020-03-26) | +13.65% (2020-06-08) | +15.80% (2020-03-26) | +20.49% (2020-03-26) |
| `volume` median / max | 79,861,500 / 1,432,993,400 | 51,132,400 / 444,085,400 | 98,282,200 / 907,054,600 | 154,659,500 / 1,073,661,600 |
| `adjclose / close`: min → max | 0.8123 → 1.0 | 0.7139 → 1.0 | 0.6206 → 1.0 | 0.6456 → 1.0 |
| `adjclose == close` from | 2026-08-31 | 2026-03-25 | 2026-09-16 | 2026-04-21 |

**Trading-date alignment (verified).** All four daily files contain **exactly the same 1,887 dates**: the intersection equals the union,
and no ticker is missing a date. Shared calendar properties:
- weekdays only (Mon 379, Tue 386, Wed 379, Thu 375, Fri 368);
- rows per year 2019: 258, 2020: 242, 2021: 247, 2022: 246, 2023: 239, 2024: 237, 2025: 236, 2026 (to Oct 8): 182;
- the same calendar-gap profile, with the largest gap 2025-03-27 → 2025-04-08 (12 days). Gaps of 8 days or more fall in March to May, which is consistent with Eid closures **(inferred; not checked against an official IDX calendar)**.

**Weekly and monthly files:** 406 weekly rows (labels 2018-12-31 → 2026-10-05, all Mondays) and 94 monthly rows (labels 2018-12-31 → 2026-09-30,
all month-ends) for **every** ticker. They have 0 nulls, 0 duplicates and 0 OHLC violations. Two weekly rows are zero-volume flat bars (2024-04-08 and
2025-03-31) in every ticker.

## 6. Data Quality and Source Limitations

### Observed (verified in this snapshot)
1. **Weekly and monthly labels are offset from their periods (all four tickers).** I verified this by re-aggregating the daily data:
   - **Monthly:** a row labeled `YYYY-MM-<last day>` contains the **next** calendar month. Close and volume match **94/94** for every ticker. Open, high and low match 83–94/94 (vendor differences of about 0.1–1.3% in the samples inspected).
   - **Weekly:** a Monday label `D` aggregates the daily rows from `D+1` to `D+7`. Close and volume match **404/404** for every ticker; open matches 390–393. Aligning to `D..D+6` instead matches only 46–70 closes.
   - The likely cause is a time-zone shift in the upstream export **(inferred)**.
2. **Partial trailing periods (all four).** Weekly `2026-10-05` holds 3 sessions (Oct 6–8). Monthly `2026-09-30` is October 2026 to date (6 sessions).
3. **Holidays are represented inconsistently.**
   - 13 zero-volume, flat rows in 2019 (2019-01-01, 02-05, 03-07, 04-03, 04-17, 04-19, 05-01, 05-30, 06-03 → 06-07) occur in **all four** tickers. They look like exchange holidays **(inferred)**.
   - After mid-2019, holidays are simply absent.
4. **Gaps in individual tickers' data.** There are extra zero-volume, flat rows on **2020-03-13** (BBCA, BBNI) and **2020-03-16** (BBCA, BMRI). On those same dates the other banks show normal volume (for example BBRI 295,725,807 and 196,265,939), so the market was open. These are vendor gaps, not closures. *(This corrects the earlier BBCA-only note, which called them "unexplained".)*
5. **Prices are retroactively adjusted, and no as-traded price is available.**
   - `close` is back-adjusted for corporate actions: no unadjusted split jump appears (no daily move above 20.5%).
   - The adjustment windows end on 2023-10-05 for BBNI (`.5` values), 2023-04-03 for BMRI (`.5` values) and 2021-09-07 for BBRI (non-tick values). These are consistent with 2-for-1 splits for BBNI and BMRI and a rights issue for BBRI **(inferred; the corporate actions were not verified)**.
   - `adjclose` adds dividend adjustment; its ratio to `close` rises to 1.0 at each ticker's latest adjustment date.
6. **Float32 precision** in every price and `adjclose` value (§4).
7. **`adjclose` is not stable across versions.** `mode: full` re-extracts the history daily, so past `adjclose` values (and `close`, after a new corporate action) can change from one download to the next.
8. **Naming:** `Date` is capitalized while the other columns are lowercase. There is no ticker column.

### Risks that still need testing
- Whether Databricks reads the Parquet `TIMESTAMP(NANOS)` column. To be tested in D1-04; this is the main reason for the CSV-first recommendation.
- Whether partial-day sessions could appear if the upstream extraction time changes.
- Upstream schema drift (column renames or additions) or Yahoo outages.
- The `volume` unit (shares vs lots) and whether volume is adjusted for corporate actions. Both are assumed, not documented.
- Row counts and historical values changing on refresh (rewritten history rather than appended days).

## 7. Four-Dataset Compatibility Assessment

| # | Question | Answer (evidence) |
| - | -------- | ----------------- |
| 1 | Are the daily-price schemas compatible? | **Yes.** All 8 column names, the CSV column order, the CSV formats and the Parquet schemas are identical (§4). Only the decimal precision differs (cosmetic). |
| 2 | Do ticker identifiers need adding at ingestion? | **Yes.** No record carries a ticker. Derive it from the file name (`<T>.JK.csv`) or directory, and cross-check against `run-summary.json` `ticker`. |
| 3 | Is date coverage aligned enough to compare? | **Yes, fully.** There are 1,887 identical trading dates across all four (2019-01-01 → 2026-10-08). The ticker-specific zero-volume gap rows (§6.4) still need a rule. |
| 4 | Are adjusted and unadjusted prices available and consistent? | **Both `close` (corporate-action-adjusted) and `adjclose` (plus dividends) exist for all four,** with the same convention. **No as-traded price exists.** For performance comparisons across banks, `adjclose` (total return) is the consistent basis; `close` gives price return. This is a formula decision (§9). |
| 5 | Do the weekly and monthly quirks match BBCA? | **Yes, for all four:** the same label offsets, partial trailing bars, holiday-week zero-volume bars, and small open/high/low vendor differences. |
| 6 | Which files should be the primary input? | **Recommendation (not a decision): the 4 daily CSVs.** They are equivalent to Parquet (0 cell mismatches), avoid the nanosecond-timestamp risk, and are easy to inspect. Keep the daily Parquet files and all weekly/monthly files and JSON in Bronze as reference and reconciliation inputs. **Derive** analytical weekly and monthly aggregates from validated daily data. The final format choice belongs to OD-05. |

## 8. Proposed Bronze, Silver and Gold Mapping (design proposal only, not implemented)

- **Bronze:** land all 40 source files unchanged per download snapshot. Add file-level provenance: source slug, ticker, file name, file checksum, source `run_id` (from `run-summary.json`), `ingested_at_utc`, load timestamp and pipeline run ID. Kaggle `lastUpdated` is not in the landed files; it is recorded in documentation at download time only (§1). Load the daily CSVs into a Bronze table with `ticker` derived from the file. Keep the JSON `dq` blocks in an ops/reference table for reconciliation. Because each source version rewrites history, load each download as a whole snapshot rather than appending to earlier ones.
- **Silver:**
  - Normalize the names (`trade_date`, snake_case), types (`DATE`, `DOUBLE`/`DECIMAL`, `BIGINT`) and `ticker`.
  - Enforce unique (`ticker`, `trade_date`); validate OHLC consistency, positive prices, non-negative volume and no nulls.
  - Flag zero-volume flat rows as non-trading rather than silently deleting them, with documented rules for holiday rows vs ticker-specific vendor gaps.
  - Reconcile the derived weekly and monthly aggregates with the source files (using the label offsets in §6.1) as a DQ check.
  - Flag partial trailing periods.
- **Gold:** comparative datasets at a documented grain (`ticker × trade_date`, plus derived `ticker × month`): normalized price index, daily and monthly returns, rolling volatility, and trading volume summaries (§9). The table design and grain belong to **OD-08**.

## 9. Proposed Business Metrics (candidates, not approved KPIs)

> **The final definitions are in [`docs/KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md) (DEC-03, owner-approved 2026-10-09).** The table below is the
> original candidate assessment, kept for traceability.

The final KPI formulas were decided in **DEC-03** ([`docs/KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md)). "Supported" below means the schema contains the inputs.

| Candidate | Supported? | Proposed formula | Decisions still needed |
| --------- | ---------- | ---------------- | ---------------------- |
| Normalized price index | Yes | `100 × P(t) / P(base)` per ticker | Price basis (`adjclose` total return vs `close` price return); base date (first common date of the selected window; all dates are shared); snapshot dependence (history is rewritten on refresh) |
| Daily return | Yes | `P(t) / P(t−1) − 1` over consecutive trading rows per ticker | Simple vs log; whether to exclude zero-volume flat rows. *Correction:* flat rows carry the previous close, so the next day's return still equals the true return over the gap and cumulative returns are unaffected. The actual problem is that each flat row adds an artificial 0% observation (understating volatility and miscounting sessions) and, for the 2020 vendor gaps, hides real movement. |
| Monthly return | Yes, derived from daily | `P(last session of month) / P(last session of previous month) − 1` | Use derived months, not the source monthly files (§6.1); flag the partial current month; first month has no prior month |
| Rolling volatility | Yes | Standard deviation of daily returns over N trading rows, optionally annualized by `√A` | Window N (for example 20 or 60); annualization factor (the common convention of 252 vs about 236–247 observed sessions per year); sample vs population standard deviation |
| Trading volume | Yes (raw units) | Sum or average of `volume` per period and ticker | Units (shares assumed); share counts differ by bank, so compare relative changes, not raw levels; no traded value or shares outstanding (so no market cap or turnover ratio); `close × volume` is only an approximation because prices are adjusted |

## 10. Reproducibility and Source Attribution

**Prerequisites:** a Kaggle account; Kaggle CLI 2.x (this project used 2.2.4, installed with `uv tool install kaggle`); credentials configured as
described in the Kaggle CLI documentation (<https://github.com/Kaggle/kaggle-cli/tree/main/docs>; for example `kaggle auth login`, the `KAGGLE_API_TOKEN` environment variable, or `~/.kaggle/access_token`). Never commit credentials.

**Download (run from the repository root).** The full setup is in [`README.md`](../README.md) ("Reproduce it").
```bash
kaggle datasets download caesarmario/bank-central-asia-stock-historical-price -p /tmp/bbca-dl
```
```bash
unzip -n /tmp/bbca-dl/bank-central-asia-stock-historical-price.zip -d data/raw/bbca/
```
Repeat for the other three tickers, using their slugs (§1) and the target directories `data/raw/bbni/`, `data/raw/bmri/` and `data/raw/bbri/`. Then check completeness:
```bash
kaggle datasets files caesarmario/bank-central-asia-stock-historical-price
```
```bash
ls -l data/raw/bbca/
```
Compare the names and sizes; checksums can be recorded with `sha256sum data/raw/*/*`. A later download is a **newer snapshot**: its row counts, sizes and
historical `adjclose` values will differ from §3–§5.

**Profiling method.** Read-only Python scripts run with `-I`, kept outside the repository. CSVs were read with the standard-library `csv` module; Parquet with
`pyarrow` in a throwaway `uv run --no-project --with pyarrow` environment (nothing installed into the project). The checks were: inferred types; null and empty
counts; duplicate rows and dates; sort order; weekday and calendar-gap profile; OHLC validity; zero and negative values; float32 exactness; adjustment
ratios and windows; cell-by-cell CSV↔Parquet equality; Parquet physical types; daily→weekly and daily→monthly re-aggregation; cross-ticker
date alignment; and agreement with the JSON `dq` blocks. Raw-file SHA-256 checksums were identical before and after profiling.

**Attribution:** data by Kaggle user `caesarmario`, sourced from Yahoo Finance, under the Kaggle license label `world-bank` (upstream terms unresolved, §2).

**Public repository:** the raw files under `data/` must **not** be committed. Another developer obtains the data independently with the commands above.
Publishing code, documentation, aggregate results and screenshots is the intended approach. Whether that is fully permitted depends on the unresolved upstream
terms, which is recorded in [`docs/LIMITATIONS.md`](LIMITATIONS.md) rather than treated as settled.
