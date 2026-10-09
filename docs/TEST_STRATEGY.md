# Test Strategy

> **Status:** owner-approved (DEC-10, 2026-10-09): **in-workspace tests + DQ checks + reconciliation**. Implementation is pending.
> All "expected" values are predictions derived from `docs/DATASET.md` and `docs/KPI_DEFINITIONS.md`, to be verified on Databricks.
> The four sections follow the verification concerns in `CLAUDE.md`, which are reported separately.

## 1. Code Correctness (REQ-26, SHOULD)

- Transformation logic lives in **pure functions in `.py` modules** in the repo. Notebooks import and call them.
- The notebook `tests/run_unit_tests` builds small hand-made DataFrames and checks the results with plain `assert` statements (no extra libraries).
- Window sizes are function parameters, so tests use **window 3** and hand-computed values.
- **Cases:**
  - `volume_status` classification;
  - NULL daily return on flagged rows, and a return computed from the previous normal row;
  - base-date selection;
  - rolling volatility: leading NULLs and value;
  - drawdown is 0 on a new peak;
  - monthly and yearly returns and `is_partial`;
  - relative volume excludes day t;
  - a malformed date cast goes to quarantine.
- **To verify in the first notebook:** whether serverless notebooks can import `.py` files from a Git folder. Fallback: `%run` a functions notebook.

## 2. Data Quality (REQ-08, MUST)

Results for every run go to **`ops.dq_results`** (`pipeline_run_id`, `check_name`, `layer`, `severity`, `passed`, `failing_count`, `expected`, `details`, `checked_at`), as defined in `docs/DATA_MODEL.md` §3.

### Draft catalog

| Layer | Severity | Check | Expected |
| ----- | -------- | ----- | -------- |
| Bronze | CRITICAL | All 4 tickers present | 4 |
| Bronze | CRITICAL | Per-ticker row count equals the daily row count in `run-summary.json` (an independent source) | Equal |
| Bronze | CRITICAL | The `run-summary.json` `ticker` field (the source symbol, for example `BBCA.JK`) equals the config `source_symbol` for that ticker | Equal |
| Bronze | CRITICAL | Each CSV header line equals `source_columns` (exact names and order) | 0 mismatches |
| Bronze | WARN | Exactly one distinct source `run_id` across the four tickers | 1 |
| Bronze | WARN | Rows with a non-null `_rescued_data` | Expected 0 |

Implemented Bronze check names (`notebooks/01_bronze_ingest.py`): `bronze_all_tickers_present`, `bronze_header_matches`,
`bronze_rows_match_run_summary`, `bronze_source_symbol_matches` (CRITICAL); `bronze_single_source_run_id`, `bronze_rescued_data_empty` (WARN).
| Silver | CRITICAL | `silver_no_duplicate_keys`: no duplicate (`ticker`, `trade_date`) among valid rows (duplicates stop the run; they are not quarantined) | 0 |
| Silver | CRITICAL | `silver_reconciles_with_bronze`: Silver rows + quarantine rows = Bronze rows | Equal |
| Silver | CRITICAL | `silver_no_nulls`: no NULL in `ticker`, `trade_date`, the 5 prices, `volume`, `volume_status` | 0 |
| Silver | CRITICAL | `silver_positive_prices`: prices > 0 (logic guard; violating rows should already be quarantined) | 0 violations |
| Silver | CRITICAL | `silver_ohlc_valid`: `low <= min(open, close) and max(open, close) <= high` (logic guard) | 0 violations |
| Silver | CRITICAL | `silver_volume_non_negative`: `volume >= 0` (logic guard) | 0 violations |
| Silver | WARN | `silver_quarantine_empty`: quarantine rows (details: counts per reason) | Expected 0 |
| Silver | WARN | `silver_same_date_set`: every ticker has the same set of trade dates | Expected identical |
| Silver | WARN | `silver_zero_volume_rows_flat`: zero-volume rows not flat, or close != previous close | Expected 0 |
| Silver | WARN | `silver_flat_rows_adjclose_carried`: zero-volume rows whose adjclose != previous adjclose | Expected 0 |
| Silver | WARN | `silver_zero_partial_count`: `zero_partial` rows (expected to report the known vendor gaps; WARN never blocks) | Expected 4 |
| Silver | WARN | `silver_source_ingested_at_parsed`: rows where `ingested_at_utc` did not parse as TIMESTAMP | Expected 0 |
| Silver | INFO | `silver_zero_all_tickers_count`: `zero_all_tickers` rows | Expected 52 |
| Silver | INFO | `silver_base_date`: computed base date (G3) | Expected 2019-01-02 (to verify) |
| Gold | CRITICAL | `gold_unique_keys`: key uniqueness in each of the 5 tables (details per table) | 0 duplicates |
| Gold | CRITICAL | `gold_daily_rows_match_silver`: `fact_daily_metrics` rows = Silver rows with `trade_date >= base_date` | Equal (expected 7,544) |
| Gold | CRITICAL | `gold_index_100_at_base`: `normalized_index = 100` at the base date (abs diff ≤ 1e-9) | All 4 tickers |
| Gold | CRITICAL | `gold_drawdown_non_positive`: `drawdown <= 1e-12` | 0 violations |
| Gold | CRITICAL | `gold_summary_four_rows`: `ticker_summary` holds exactly the configured tickers | 4 |
| Gold | CRITICAL | `gold_total_return_consistent`: `total_return` = last `normalized_index / 100 - 1` (abs diff ≤ 1e-9) | Equal |
| Gold | CRITICAL | `gold_single_source_run_id`: exactly one distinct `source_run_id` in Silver | 1 |
| Gold | WARN | `gold_monthly_compounds_to_yearly`: `exp(sum(log(1 + monthly_return)))` per ticker-year = `1 + yearly_return` (abs diff ≤ 1e-9) | Within tolerance |
| Gold | WARN | `gold_vol_leading_nulls`: normal rows before the first non-NULL `vol_60d_ann` per ticker | 60 |
| Gold | INFO | `gold_partial_periods`: `is_partial` months and years per ticker | 2 months and 2 years per ticker |

### Blocking behavior
- A failed CRITICAL check raises an error in its task, and the Job skips the downstream tasks.
- The Gold task computes its DataFrames, runs the Gold checks on them, and **overwrites the Gold tables only if every CRITICAL check passes**,
  so Gold is never partially published (REQ-12).

## 3. Pipeline Execution (REQ-09, REQ-12, MUST)

- **End-to-end run:** run the Job end to end and record its run ID.
- **Rerun test (idempotency, D2-07):**
  1. Run the Job twice on the same input.
  2. Run `notebooks/91_rerun_check` (read-only). For each of the 9 Bronze, Silver and Gold tables it uses **Delta time travel** to compare
     the latest data-writing version with the previous one, and reports which versions were compared. Maintenance versions (OPTIMIZE, VACUUM, …)
     are skipped; a table without a previous version is SKIPPED, which makes the overall result FAIL.
  3. Run-specific columns are excluded (`pipeline_run_id`, `bronze_pipeline_run_id`, `bronze_loaded_at`, `processed_at`, `quarantined_at`, `built_at`).
  4. Per table:
     - row counts must be equal;
     - keys must be unique in the latest version;
     - a full outer join on the key must find 0 rows missing on either side;
     - non-DOUBLE columns must match exactly (null-safe `<=>`);
     - DOUBLE columns must agree within **1e-9** (NULL equals NULL), because the evaluation order of floating-point aggregations
       (stddev, avg) can vary between runs.
  5. The quarantine table has no key and is compared by row count only.
  6. Expect `RERUN CHECK PASS`. The notebook also shows the last two `gold_build` `pipeline_run_id`s, which link the comparison to the two Job runs.
     Logic: `src/bank_pipeline/rerun.py`.
- **Induced failure test** (owner decision 2026-10-10, option A):
  1. A notebook creates a test landing folder with a copy of the 8 landed files, in which **one data row of one ticker's CSV is replaced** by a copy of
     another row of the same ticker. The row count stays at 1,887, so the Bronze checks pass (an *added* row would trip
     `bronze_rows_match_run_summary` first).
  2. Run the Job with the job parameter `landing_path` pointing to that folder.
  3. Expected:
     - `bronze_ingest` succeeds and **overwrites Bronze with the fixture data**;
     - `silver_transform` fails on `silver_no_duplicate_keys` and writes nothing;
     - `gold_build` is skipped;
     - Silver and Gold keep the previous run's data (their `pipeline_run_id` is unchanged).
  4. Recovery: rerun the Job with the real `landing_path`, which restores Bronze from the real files and rebuilds Silver and Gold.
  5. Record both run IDs.
  6. **Runbook note:** between the failed run and the recovery run, Bronze holds the fixture data while Silver and Gold still hold the previous good
     data. The window ends when the recovery run's `bronze_ingest` finishes.

## 4. Business-Metric Correctness (REQ-16, MUST)

- Independent SQL on Silver for the headline KPIs (total return, full-period volatility, max drawdown, and one yearly return), compared with the
  Gold values and with the dashboard values.
- Cross-check against the local profile: 1,887 rows per ticker, and the first and last `close` values in `docs/DATASET.md` §5.
- Results go into a reconciliation table under `docs/evidence/`.

## Rationale

- There is no confirmed local Spark/Java on the owner's machine, and Databricks Connect would need a token. Running the tests on the same
  serverless runtime as the pipeline avoids both.
- **Cost:** tens of seconds of compute per test run, and code must be pulled into the Git folder first.
- **Cut list:** only the unit tests (cut-list item 4) may be dropped. DQ checks, the rerun test, the failure test and reconciliation are **never cut**.
