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
| Gold | CRITICAL | Key uniqueness per table | 0 duplicates |
| Gold | CRITICAL | `normalized_index = 100` at the base date | All 4 tickers |
| Gold | CRITICAL | `drawdown <= 0` | 0 violations |
| Gold | CRITICAL | `ticker_summary` has exactly 4 rows | 4 |
| Gold | CRITICAL | `total_return` equals the last `normalized_index / 100 - 1` | Equal (within float tolerance) |
| Gold | WARN | Product of `(1 + monthly_return)` within a year equals `1 + yearly_return` | Within tolerance |
| Gold | WARN | Exactly 60 leading NULLs of `vol_60d_ann` per ticker | 60 |

### Blocking behavior
- A failed CRITICAL check raises an error in its task, and the Job skips the downstream tasks.
- The Gold task computes its DataFrames, runs the Gold checks on them, and **overwrites the Gold tables only if every CRITICAL check passes**,
  so Gold is never partially published (REQ-12).

## 3. Pipeline Execution (REQ-09, REQ-12, MUST)

- **End-to-end run:** run the Job end to end and record its run ID.
- **Rerun test (idempotency):**
  1. Run the Job twice on the same input.
  2. Compare per-table row counts and a content checksum (the sum of row hashes, excluding the run-metadata columns).
  3. Expect identical values and 0 duplicate keys.
- **Induced failure test:**
  1. A notebook creates a test landing folder containing a copy of the CSVs plus one duplicated key row.
     > **Note (agent, for owner review):** as implemented, an *added* duplicate row would make the CSV row count differ from
     > `run-summary.json`, so the **Bronze** CRITICAL check `bronze_rows_match_run_summary` would fail first and Silver would never run.
     > To exercise the Silver duplicate-key path, the test copy should **replace** one data row with a copy of another row of the same
     > ticker (the count stays at 1,887). Alternatively, accept a Bronze-level failure as the induced failure. Decision pending.
  2. Run the Job with the job parameter `landing_path` pointing to that folder.
  3. Expect the Silver duplicate-key check to fail, the Gold tasks to be skipped, and the Gold `pipeline_run_id` to stay unchanged.
  4. Rerun with the correct path to recover.
  5. Record both run IDs.

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
