# Data-Quality Check Catalog

> Every check implemented in the pipeline (Bronze 6, Silver 14, Gold 10), with its rule, severity, action and the latest recorded result.
> Results are persisted per run in `ops.dq_results` (`pipeline_run_id`, `check_name`, `layer`, `severity`, `passed`, `failing_count`, `expected`,
> `details`, `checked_at`). Results below are owner-reported in the cited evidence files.

**Actions.**
- **CRITICAL:** if failed, the task raises **before writing** its tables, records a FAILED audit row, and the Job skips the downstream tasks (block).
- **WARN:** recorded only, never blocks.
- **INFO:** recorded only; `passed` is always true, and `failing_count` carries a count for monitoring.

**Runs referenced.**

| Run | Description | Evidence |
| --- | ----------- | -------- |
| Job run **1066568616292788** | First full Job run; per-layer check results recorded: Bronze 6 (0 failed), Silver 14 (1 failed: the expected WARN), Gold 10 (0 failed) | `docs/evidence/d2-06-job.md` |
| Job runs **371194405323795**, **318690159636842**, **766912259782044** | Later successful runs (rerun test, failure recovery, DEC-14 rebuild); every task succeeded, so no CRITICAL check failed. Per-check WARN values were not recorded for these runs | `d2-07-rerun.md`, `d2-09-failure-test.md`, `d2-05-gold.md` |
| Job run **164942117421206** | Induced failure (fixture with one duplicated BBCA key) | `docs/evidence/d2-09-failure-test.md` |

## Bronze (`notebooks/01_bronze_ingest.py`)

| Check | Severity | Rule | Normal data (run 1066568616292788) | Induced failure (run 164942117421206) |
| ----- | -------- | ---- | ---------------------------------- | ------------------------------------- |
| `bronze_all_tickers_present` | CRITICAL | All 4 configured tickers are present in the CSV rows and in the run summaries | Passed | Passed |
| `bronze_header_matches` | CRITICAL | Each CSV header equals the configured 8 source columns (names and order) | Passed | Passed |
| `bronze_rows_match_run_summary` | CRITICAL | Per ticker: CSV data rows = daily row count in the source's `run-summary.json` | Passed (1,887 = 1,887 per ticker) | Passed (the fixture replaces a row, so the count is unchanged) |
| `bronze_source_symbol_matches` | CRITICAL | `run-summary.json` ticker (for example `BBCA.JK`) = configured source symbol | Passed | Passed |
| `bronze_single_source_run_id` | WARN | Exactly one distinct source run ID across the four tickers | Passed | Passed |
| `bronze_rescued_data_empty` | WARN | No rows with values outside the schema (`_rescued_data`) | Passed (0) | Passed |

## Silver (`notebooks/02_silver_transform.py`)

| Check | Severity | Rule | Normal data (run 1066568616292788; values from `d2-03-silver.md`) | Induced failure (run 164942117421206) |
| ----- | -------- | ---- | ----------------------------------------------------------------- | ------------------------------------- |
| `silver_no_duplicate_keys` | CRITICAL | No duplicate (`ticker`, `trade_date`) among valid rows; duplicates stop the run | Passed | **Failed**, failing_count 1 (`BBCA@2019-05-17x2`). The run stopped, and Silver and Gold were not written |
| `silver_reconciles_with_bronze` | CRITICAL | Silver rows + quarantine rows = Bronze rows | Passed (7,548 = 7,548 + 0) | Passed (7,548 = 7,548 + 0) |
| `silver_no_nulls` | CRITICAL | No NULL in key, prices, volume, volume_status | Passed | Passed |
| `silver_positive_prices` | CRITICAL | All prices > 0 (guard: violating rows should already be quarantined) | Passed | Passed |
| `silver_ohlc_valid` | CRITICAL | `low <= min(open, close) and max(open, close) <= high` (guard) | Passed | Passed |
| `silver_volume_non_negative` | CRITICAL | `volume >= 0` (guard) | Passed | Passed |
| `silver_quarantine_empty` | WARN | Quarantined rows, with counts per reason code | Passed (0) | Passed |
| `silver_same_date_set` | WARN | Every ticker has the same set of trade dates | Passed | **Failed**, 1 (BBCA had 1,886 dates: the replaced row's date was missing) |
| `silver_zero_volume_rows_flat` | WARN | Zero-volume rows are flat at the previous close | Passed (0) | Passed |
| `silver_flat_rows_adjclose_carried` | WARN | Zero-volume rows carry the previous `adjclose` | Passed (0) | Passed |
| `silver_zero_partial_count` | WARN | Rows with zero volume on a day other tickers traded (vendor gaps); expected to report the known gaps | Reported 4 (expected) | Reported 4 |
| `silver_source_ingested_at_parsed` | WARN | `ingested_at_utc` parses as TIMESTAMP | Passed (0) | Passed |
| `silver_zero_all_tickers_count` | INFO | Rows on dates on which all four banks show zero volume (likely exchange holidays; inferred, not checked against the IDX calendar) | 52 | 52 |
| `silver_base_date` | INFO | Computed base date (first date on which all tickers traded) | 2019-01-02 | Passed (INFO; value not recorded) |

## Gold (`notebooks/03_gold_build.py`)

The Gold checks run on the computed DataFrames before anything is written. In the induced-failure run the `gold_build` task was skipped.

| Check | Severity | Rule | Normal data (run 1066568616292788; values from `d2-05-gold.md`) |
| ----- | -------- | ---- | --------------------------------------------------------------- |
| `gold_unique_keys` | CRITICAL | Key uniqueness in each of the 5 Gold tables | Passed (0 duplicates) |
| `gold_daily_rows_match_silver` | CRITICAL | `fact_daily_metrics` rows = Silver rows from the base date | Passed (7,544 = 7,544) |
| `gold_index_100_at_base` | CRITICAL | `normalized_index` = 100 at the base date for every ticker (abs diff ≤ 1e-9) | Passed |
| `gold_drawdown_non_positive` | CRITICAL | `drawdown <= 1e-12` | Passed |
| `gold_summary_four_rows` | CRITICAL | `ticker_summary` holds exactly the 4 configured tickers | Passed |
| `gold_total_return_consistent` | CRITICAL | `total_return` = last `normalized_index` / 100 − 1 (abs diff ≤ 1e-9) | Passed |
| `gold_single_source_run_id` | CRITICAL | Exactly one distinct source run ID in Silver | Passed |
| `gold_monthly_compounds_to_yearly` | WARN | Compounded monthly returns equal the yearly return per ticker-year (abs diff ≤ 1e-9) | Passed |
| `gold_vol_leading_nulls` | WARN | Exactly 60 leading NULL `vol_60d_ann` normal rows per ticker | Passed (60 per ticker) |
| `gold_partial_periods` | INFO | Partial months and years per ticker | 16 (2 months + 2 years per ticker) |

## Related checks outside the pipeline

- Validation queries: `sql/validation/01_bronze.sql`, `02_silver.sql`, `03_gold.sql` (including G9: every `peak_date` is a normal trading day), and
  `05_failure_test.sql`; Gold table and column comments (metadata, not a data-quality check): `07_metadata.sql`.
- Dashboard reconciliation: `sql/validation/06_dashboard_reconciliation.sql` (`docs/evidence/d3-03-dashboard-reconciliation.md`).
