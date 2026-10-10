# Data Model

> **Status:** implemented and verified in Databricks (Gold design: DEC-08; see `docs/DECISIONS.md`). Row counts quoted here are those recorded for
> the 2026-10-08 snapshot in `docs/evidence/` (Bronze/Silver 4 × 1,887, Gold daily 7,544, monthly 376, yearly 32). The full **data dictionary**
> (every column with type and description) is in §5.
>
> Related: KPI formulas in [`docs/KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md) (DEC-03); tests and DQ checks in
> [`docs/TEST_STRATEGY.md`](TEST_STRATEGY.md) and [`docs/DQ_CATALOG.md`](DQ_CATALOG.md); configuration in `config/pipeline.json`.

## 0. Landing (source files in Databricks)

- Unity Catalog Volume **`workspace.bronze.landing`**, path `/Volumes/workspace/bronze/landing/<folder>/`, with `folder` = `bbca`, `bbni`,
  `bmri`, `bbri` (the same layout as the local `data/raw/`).
- Files per folder (DEC-05): `<TICKER>.JK.csv` and `run-summary.json`, **8 files in total**.
- Files are overwritten on re-download (full refresh, DEC-06).
- **Test fixtures (not pipeline input):** the separate Volume `workspace.bronze.test_fixtures` holds the induced-failure fixture
  (`failure_dup_key/`, built by `notebooks/90_make_failure_fixture`); it is used only through a `landing_path` override (`docs/RUNBOOK.md`).

## 1. Bronze

| Table | Grain | Columns | Notes |
| ----- | ----- | ------- | ----- |
| `bronze.daily_prices_raw` | One row per source CSV data row | `source_date`, `open`, `high`, `low`, `close`, `adjclose`, `volume`, `ingested_at_utc` (all **STRING**, original values preserved), `ticker` (derived from the landing folder), `source_file`, `bronze_loaded_at`, `pipeline_run_id`, `_rescued_data` | Permissive typing, so no source value is lost; typing happens in Silver. `_rescued_data` (Databricks CSV option `rescuedDataColumn`) captures values that do not fit the 8-column schema; expected empty (Bronze WARN check). |
| `bronze.source_run_summary` | One row per ticker | `ticker`, `source_symbol`, `stock`, `source_run_id`, `daily_rows`, `daily_date_max` (STRING, as in the source), `daily_duplicate_dates`, `raw_json` (string), `source_file`, `bronze_loaded_at`, `pipeline_run_id` | `ticker` is the project ticker from the config (landing folder → ticker, for example `bbca` → `BBCA`). Mapping from `run-summary.json`: JSON `ticker` → `source_symbol` (for example `BBCA.JK`; the Bronze DQ check compares it with the config `source_symbol`); `stock` → `stock`; `run_id` → `source_run_id`; ``intervals.`1d`.rows`` → `daily_rows`; ``intervals.`1d`.date_max`` → `daily_date_max` (format `YYYY-MM-DD HH:MM:SS`); ``intervals.`1d`.duplicate_dates`` → `daily_duplicate_dates`. Schema confirmed by the D1-11 smoke test (`docs/evidence/d1-11-landing-smoke-test.md`). |

## 2. Silver and Quarantine

| Table | Grain (key) | Columns | Notes |
| ----- | ----------- | ------- | ----- |
| `silver.daily_prices` | `ticker`, `trade_date` | `ticker`, `trade_date` DATE, `open`/`high`/`low`/`close`/`adjclose` DOUBLE, `volume` BIGINT, `volume_status`, `source_ingested_at` TIMESTAMP, `source_file`, `source_run_id`, `pipeline_run_id`, `processed_at` | **DOUBLE, not DECIMAL:** source values are float32 stored as double, so DECIMAL adds no real precision; all KPIs are ratios; equality checks use a tolerance. `volume_status` per `docs/KPI_DEFINITIONS.md` G4. |
| `silver.daily_prices_quarantine` | One row per rejected Bronze row | Bronze columns as stored (with Bronze's `pipeline_run_id` renamed `bronze_pipeline_run_id`), `reject_reason`, `pipeline_run_id` (the Silver run), `quarantined_at` | Overwritten each run (written even when empty); the counts are kept historically in `ops`. `reject_reason` = `;`-joined codes: `invalid_date`, `invalid_price` (any of the 5 prices NULL after `try_cast`), `non_positive_price`, `invalid_volume` (NULL or < 0), `ohlc_inconsistent`, `rescued_data_present`. |

**Typing:** `try_cast` (not `cast`/`to_date`), because serverless runs with ANSI mode, where a plain cast raises on bad input; a NULL result becomes a
reject reason. **Duplicate keys are not quarantined:** a duplicated (`ticker`, `trade_date`) means the source snapshot is broken, so the CRITICAL
check `silver_no_duplicate_keys` stops the run before anything is written.

## 3. ops (run audit and DQ results)

| Table | Key | Columns | Notes |
| ----- | --- | ------- | ----- |
| `ops.run_audit` | `pipeline_run_id`, `task_name` | `job_run_id`, `started_at`, `ended_at`, `status`, `rows_in`, `rows_out`, `rows_rejected`, `error_message` | Append-only |
| `ops.dq_results` | `pipeline_run_id`, `check_name` | `layer`, `severity`, `passed`, `failing_count`, `expected`, `details`, `checked_at` | Append-only |

**`pipeline_run_id`:** taken from the Job parameter `{{job.run_id}}` (verified on Free Edition, `docs/evidence/d2-06-job.md`); a UUID when a notebook runs interactively.

## Source-to-Target Mapping

| Source (daily CSV / JSON) | Bronze | Silver | Gold |
| ------------------------- | ------ | ------ | ---- |
| CSV `Date` | `source_date` STRING | `trade_date` DATE | `trade_date`, `year`, `month`, `month_start` |
| CSV `open`, `high`, `low`, `close`, `adjclose` | STRING | DOUBLE | `close`, `adjclose` and the KPIs (§4) |
| CSV `volume` | STRING | BIGINT | `volume`, `rel_volume_60d`, `avg_daily_volume` |
| CSV `ingested_at_utc` | STRING | `source_ingested_at` TIMESTAMP | `source_ingested_at` = max per snapshot |
| Landing folder (`bbca`, …) → config ticker; file path (`_metadata.file_path`) | `ticker`, `source_file` | `ticker`, `source_file` | `ticker` |
| `run-summary.json` `run_id` | `bronze.source_run_summary.source_run_id` | `source_run_id` | `source_run_id` |
| `run-summary.json` `ticker`, ``intervals.`1d`.*`` | `bronze.source_run_summary.source_symbol`, `daily_rows`, `daily_date_max`, `daily_duplicate_dates` | (used by Bronze DQ checks only) | — |
| (derived) | — | `volume_status` | `volume_status` |
| (pipeline) | `pipeline_run_id`, `bronze_loaded_at` | `pipeline_run_id`, `processed_at` | `pipeline_run_id`, `built_at` |

The Gold columns are defined in §4.

## Job

Four sequential tasks: **`setup` → `bronze_ingest` → `silver_transform` → `gold_build`**. Each task runs its layer's DQ checks on its DataFrames
before writing (DEC-10). The Job parameters `catalog` and `landing_path` override `config/pipeline.json`.

- **Definition:** [`jobs/indonesia_bank_stocks_pipeline.job.yml`](../jobs/indonesia_bank_stocks_pipeline.job.yml), exported from the Jobs UI and
  sanitized (replace `<your-email>` and `<your-user>` before use).

| Task | Notebook | Depends on |
| ---- | -------- | ---------- |
| `setup` | `notebooks/00_setup` | — |
| `bronze_ingest` | `notebooks/01_bronze_ingest` | `setup` |
| `silver_transform` | `notebooks/02_silver_transform` | `bronze_ingest` |
| `gold_build` | `notebooks/03_gold_build` | `silver_transform` |

| Job parameter | Default | Purpose |
| ------------- | ------- | ------- |
| `catalog` | `workspace` | Overrides the config catalog |
| `landing_path` | `/Volumes/workspace/bronze/landing` | Overrides the config landing path (the induced-failure test points it at a fixture folder) |
| `pipeline_run_id` | `{{job.run_id}}` | One ID shared by all tasks, the audit rows, the DQ results and the lineage columns |
| `job_run_id` | `{{job.run_id}}` | Stored in `ops.run_audit` |

- **Compute:** serverless, `PERFORMANCE_OPTIMIZED`; the queue is enabled; email on failure.
- **Retries disabled** (`disable_auto_optimization: true`, no `max_retries`): a failed CRITICAL check fails again on retry, so automatic
  retries only add cost. Transient failures are handled with Repair run.
- Evidence of a successful run: `docs/evidence/d2-06-job.md`.

## 4. Gold (DEC-08, owner-approved 2026-10-09)

One dimension plus four fact tables, each at exactly one grain.

| Table | Grain (key) | Columns | KPIs |
| ----- | ----------- | ------- | ---- |
| `gold.dim_ticker` | `ticker` | `ticker`, `bank_name`, `short_name`. 4 rows, loaded from a config file in the repo; names from `docs/DATASET.md` §1 | — |
| `gold.fact_daily_metrics` | `ticker`, `trade_date` | `close`, `adjclose`, `volume`, `volume_status`, `normalized_index`, `daily_return`, `vol_60d_ann`, `running_peak`, `drawdown`, `rel_volume_60d`, `year`, `month` | K1, K3, K4, K6, K10 |
| `gold.fact_monthly_metrics` | `ticker`, `month_start` | `monthly_return`, `avg_daily_volume`, `n_sessions`, `n_normal_sessions`, `is_partial` | K8, K11 |
| `gold.fact_yearly_metrics` | `ticker`, `year` | `yearly_return`, `n_sessions`, `is_partial` | K9 |
| `gold.ticker_summary` | `ticker` | `total_return`, `vol_full_ann`, `max_drawdown`, `peak_date`, `trough_date`, `current_drawdown`, `base_date`, `last_trade_date` | K2, K5, K7 |

### Common rules
- Every Gold table also has the lineage columns `source_run_id`, `source_ingested_at` (= `max(ingested_at_utc)` of the landed daily CSVs), `pipeline_run_id` and `built_at`.
- Full overwrite on every run (DEC-06).
- Gold rows start at the base date (`docs/KPI_DEFINITIONS.md` G3).
- **No partitioning or clustering:** 7,544 daily rows in total (4 tickers × 1,886 rows from the base date; `docs/evidence/d2-05-gold.md`), far too small to benefit.
- **No `dim_date`:** `year` and `month` are columns on the facts.
- **Column order:** as in the table above (key first, lineage last); implemented in `src/bank_pipeline/gold.py`.
- **Table and column comments (REQ-25):** applied at build time by `notebooks/03_gold_build.py` after the five tables are written, from
  `src/bank_pipeline/comments.py` (5 table comments; 48 column comments on the key, KPI and lineage columns). The overwrite replaces the table
  definition, so the comments are reapplied on every build. The statements create metadata-only Delta versions, which the rerun check skips.
  Check: `sql/validation/07_metadata.sql`.

### Implementation rules (`src/bank_pipeline/gold.py`, `notebooks/03_gold_build.py`)
- **K3, K4, K10 on normal rows only:** computed on the `normal` rows and joined back, so flagged rows get NULL. `daily_return` is NULL on the base
  date (there is no earlier normal row). `vol_60d_ann` is NULL until the window of the last 60 normal rows holds 60 non-NULL returns (expected: 60 leading
  NULL normal rows per ticker). `rel_volume_60d` is NULL until 60 previous normal rows exist (day t excluded).
- **`running_peak` and `drawdown`** use all rows (flat rows carry the previous `adjclose`, verified in `docs/evidence/d2-03-silver.md`).
- **K8/K9:** period return = `adjclose` at the last row of the period / `adjclose` at the last row of the previous period − 1; the first period
  starts at the base-date `adjclose`.
- **`is_partial`** (data-derived, no hard-coded dates): TRUE for each ticker's first period (it starts at the base date), and TRUE for the period
  containing the dataset's last `trade_date` when that date is earlier than the period's last weekday (Mon–Fri). *Conservative:* an exchange
  holiday on the last weekday would mark a complete final period as partial.
- **K7 peak and trough:** `trough_date` = date of `max_drawdown` (earliest if tied); `peak_date` = earliest `trade_date` ≤ `trough_date` whose
  `adjclose` equals the `running_peak` at `trough_date`, i.e. the day the peak was set (**DEC-14**, 2026-10-10). Flat carry-forward rows at the peak
  are excluded; the earlier rule (latest date with `drawdown = 0`) reported BBNI's zero_all_tickers row 2019-04-19. The comparison is exact because
  `running_peak` is one of the `adjclose` values and flat rows carry it unchanged.
- **Lineage:** `source_run_id` from Silver (exactly one distinct value, CRITICAL check); `source_ingested_at` = `max(source_ingested_at)` of Silver.
- **Atomicity:** each table overwrite is atomic (Delta), but not across the five tables; a failure between writes is recovered by rerunning the task.

### Relationships
- Each fact joins `dim_ticker` on `ticker`.
- Facts are **not** joined to each other: one grain per table, one visual group per table.

### Dashboard date windows
- **v1 (MUST):** KPIs are shown for fixed periods (full period, calendar year, month). The global date filter applies to the time-series visuals.
- **Not implemented in v1 (optional extension):** a Unity Catalog SQL table function such as `gold.fn_window_performance(start_date, end_date)`,
  returning per ticker the window's total return, volatility and max drawdown, called by a parameterized dashboard dataset, so the KPI logic stays in Gold.
  **Unverified on Free Edition** (SQL table functions and AI/BI dashboard parameters). If unavailable, fall back to the MUST approach.

### Rationale
- Each question Q1–Q5 is answered by single-table queries (no fact-to-fact joins), so dashboard queries stay thin (filter and select).
- Each KPI lives in exactly one place, which keeps the dashboard reconciliation simple (`docs/evidence/d3-03-dashboard-reconciliation.md`).
- A combined monthly/yearly table with a `period_type` column was **rejected** because it makes queries and key checks harder to read.


## 5. Data dictionary

Types are those produced by the code (`notebooks/00_setup.py` DDL for `ops`; the Spark DataFrames in `src/bank_pipeline/` for the other tables).
Confirm them in a workspace with `DESCRIBE TABLE <name>`. All tables are Delta tables in the catalog `workspace`.

### `bronze.daily_prices_raw`: one row per source CSV data row (7,548)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `source_date` | STRING | CSV `Date` as written in the file (`YYYY-MM-DD`) |
| `open`, `high`, `low`, `close`, `adjclose` | STRING | Prices as written in the file (`adjclose` = close adjusted for dividends and corporate actions) |
| `volume` | STRING | Traded volume as written in the file |
| `ingested_at_utc` | STRING | The source publisher's write timestamp (`YYYY-MM-DD HH:MM:SS.ffffff+00:00`) |
| `ticker` | STRING | Project ticker (BBCA, BBNI, BMRI, BBRI) from the landing folder |
| `source_file` | STRING | Path of the landed file (from `_metadata.file_path`) |
| `bronze_loaded_at` | TIMESTAMP | Load time of this Bronze write |
| `pipeline_run_id` | STRING | Pipeline run that wrote the row |
| `_rescued_data` | STRING | Values that did not fit the 8-column schema (NULL when none) |

### `bronze.source_run_summary`: one row per ticker (4)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker` | STRING | Project ticker from the landing folder |
| `source_symbol` | STRING | Ticker field of `run-summary.json` (for example `BBCA.JK`) |
| `stock` | STRING | Publisher's short stock name |
| `source_run_id` | STRING | Publisher's extraction run ID (one per snapshot) |
| `daily_rows` | BIGINT | Daily row count stated by the publisher |
| `daily_date_max` | STRING | Last daily date stated by the publisher (`YYYY-MM-DD HH:MM:SS`) |
| `daily_duplicate_dates` | BIGINT | Duplicate dates stated by the publisher |
| `raw_json` | STRING | The whole `run-summary.json` as JSON text |
| `source_file`, `bronze_loaded_at`, `pipeline_run_id` | STRING, TIMESTAMP, STRING | As in `daily_prices_raw` |

### `silver.daily_prices`: one row per (`ticker`, `trade_date`) (7,548)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker` | STRING | Project ticker |
| `trade_date` | DATE | Trading day (`try_cast` of `source_date`) |
| `open`, `high`, `low`, `close` | DOUBLE | Prices adjusted for corporate actions (as published) |
| `adjclose` | DOUBLE | Close adjusted for dividends and corporate actions; basis of all return KPIs |
| `volume` | BIGINT | Traded volume |
| `volume_status` | STRING | `normal` (volume > 0); `zero_all_tickers` (no ticker traded that day); `zero_partial` (this ticker 0 while another traded) |
| `source_ingested_at` | TIMESTAMP | Parsed `ingested_at_utc` |
| `source_file` | STRING | Landed file path |
| `source_run_id` | STRING | Publisher's run ID (from `bronze.source_run_summary`) |
| `pipeline_run_id` | STRING | Pipeline run that wrote the row |
| `processed_at` | TIMESTAMP | Silver write time |

### `silver.daily_prices_quarantine`: one row per rejected Bronze row (0 in the recorded runs)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `source_date` … `_rescued_data` | as in `bronze.daily_prices_raw` | The rejected row exactly as stored in Bronze (Bronze's run ID renamed `bronze_pipeline_run_id`) |
| `reject_reason` | STRING | `;`-joined codes: `invalid_date`, `invalid_price`, `non_positive_price`, `invalid_volume`, `ohlc_inconsistent`, `rescued_data_present` |
| `pipeline_run_id` | STRING | Silver run that quarantined the row |
| `quarantined_at` | TIMESTAMP | Silver write time |

### `gold.dim_ticker`: one row per ticker (4)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker` | STRING | Project ticker |
| `bank_name` | STRING | Full bank name (from `config/pipeline.json`) |
| `short_name` | STRING | Display name (BCA, BNI, Mandiri, BRI) |
| + lineage | | See "Lineage columns" below |

### `gold.fact_daily_metrics`: one row per (`ticker`, `trade_date`) from the base date (7,544)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker`, `trade_date` | STRING, DATE | Key |
| `close`, `adjclose` | DOUBLE | Reference price and total-return price (from Silver) |
| `volume`, `volume_status` | BIGINT, STRING | From Silver |
| `normalized_index` | DOUBLE | K1: 100 × adjclose / adjclose on the base date |
| `daily_return` | DOUBLE | K3: simple return vs the previous normal row; NULL on flagged rows and on the base date |
| `vol_60d_ann` | DOUBLE | K4: sample std. dev. of the last 60 normal-row returns × √252; NULL until 60 returns exist and on flagged rows |
| `running_peak` | DOUBLE | Highest adjclose from the base date to this day |
| `drawdown` | DOUBLE | K6: adjclose / running_peak − 1 (≤ 0) |
| `rel_volume_60d` | DOUBLE | K10: volume / mean volume of the previous 60 normal rows; NULL until available and on flagged rows |
| `year`, `month` | INT, INT | Calendar year and month of `trade_date` |
| + lineage | | See below |

### `gold.fact_monthly_metrics`: one row per (`ticker`, `month_start`) (376)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker`, `month_start` | STRING, DATE | Key (`month_start` = first day of the month) |
| `monthly_return` | DOUBLE | K8: month-end adjclose / previous month-end adjclose − 1 (first month from the base date) |
| `avg_daily_volume` | DOUBLE | K11: mean volume over normal sessions |
| `n_sessions`, `n_normal_sessions` | BIGINT, BIGINT | Rows in the month; normal rows in the month |
| `is_partial` | BOOLEAN | First month, or the month still running at the snapshot's last trade date |
| + lineage | | See below |

### `gold.fact_yearly_metrics`: one row per (`ticker`, `year`) (32)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker`, `year` | STRING, INT | Key |
| `yearly_return` | DOUBLE | K9: year-end adjclose / previous year-end adjclose − 1 (first year from the base date) |
| `n_sessions` | BIGINT | Rows in the year |
| `is_partial` | BOOLEAN | First year, or the year still running |
| + lineage | | See below |

### `gold.ticker_summary`: one row per ticker (4)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ticker` | STRING | Key |
| `total_return` | DOUBLE | K2: last adjclose / base-date adjclose − 1 |
| `vol_full_ann` | DOUBLE | K5: sample std. dev. of all daily returns × √252 |
| `max_drawdown` | DOUBLE | K7: minimum drawdown |
| `peak_date` | DATE | Day the peak before the deepest drawdown was set (DEC-14) |
| `trough_date` | DATE | Day of the deepest drawdown (earliest if tied) |
| `current_drawdown` | DOUBLE | Drawdown on the last trade date |
| `base_date`, `last_trade_date` | DATE, DATE | First and last day of the measured period |
| + lineage | | See below |

### Lineage columns (every Gold table)

| Column | Type | Description |
| ------ | ---- | ----------- |
| `source_run_id` | STRING | Publisher's run ID of the snapshot |
| `source_ingested_at` | TIMESTAMP | Latest publisher write timestamp in the snapshot |
| `pipeline_run_id` | STRING | Pipeline run that built the table |
| `built_at` | TIMESTAMP | Gold write time |

### `ops.run_audit` (append-only) and `ops.dq_results` (append-only)

| Table | Column | Type | Description |
| ----- | ------ | ---- | ----------- |
| `run_audit` | `pipeline_run_id`, `task_name`, `job_run_id` | STRING | Run and task identifiers (`job_run_id` NULL for interactive runs) |
| `run_audit` | `started_at`, `ended_at` | TIMESTAMP | Task start and end (UTC) |
| `run_audit` | `status` | STRING | `SUCCEEDED` or `FAILED` |
| `run_audit` | `rows_in`, `rows_out`, `rows_rejected` | BIGINT | Row counts of the task |
| `run_audit` | `error_message` | STRING | Error text (truncated to 2,000 characters) on failure |
| `dq_results` | `pipeline_run_id`, `check_name`, `layer`, `severity` | STRING | Run, check and layer; severity `CRITICAL`, `WARN` or `INFO` |
| `dq_results` | `passed` | BOOLEAN | Check result |
| `dq_results` | `failing_count` | BIGINT | Number of failing items (a monitored count for INFO checks) |
| `dq_results` | `expected`, `details` | STRING | Expected value and diagnostic details |
| `dq_results` | `checked_at` | TIMESTAMP | When the checks were recorded |
