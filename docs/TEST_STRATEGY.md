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

Results for every run go to **`ops.dq_results`** (`check_name`, `run_id`, `layer`, `severity`, `passed`, `failing_count`, `checked_at`).

### Draft catalog

| Layer | Severity | Check | Expected |
| ----- | -------- | ----- | -------- |
| Bronze | CRITICAL | All 4 tickers present | 4 |
| Bronze | CRITICAL | Per-ticker row count equals the daily row count in `run-summary.json` (an independent source) | Equal |
| Bronze | CRITICAL | Ticker derived from the file name equals the ticker in `run-summary.json` | Equal |
| Silver | CRITICAL | No duplicate (`ticker`, `trade_date`) | 0 |
| Silver | CRITICAL | No NULL in key and price columns | 0 |
| Silver | CRITICAL | Prices > 0 | 0 violations |
| Silver | CRITICAL | `low <= min(open, close) and max(open, close) <= high` | 0 violations |
| Silver | CRITICAL | `volume >= 0` | 0 violations |
| Silver | CRITICAL | Silver rows + quarantine rows = Bronze rows | Equal |
| Silver | WARN | Quarantine rows > 0 | Expected 0 |
| Silver | WARN | The four tickers share the same date set | Expected identical |
| Silver | WARN | Zero-volume rows whose prices are not flat | Expected 0 |
| Silver | WARN | `zero_partial` count | Expected 4 |
| Silver | INFO | `zero_all_tickers` count | Expected 52 |
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
