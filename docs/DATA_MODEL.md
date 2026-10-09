# Data Model

> **Status:** owner-approved design (Gold: DEC-08; Bronze, Silver, quarantine and `ops`: D1-09), 2026-10-09. Implementation is pending.
> Everything here is design. Row counts are expectations derived from `docs/DATASET.md`, not measured Databricks results.
>
> Related: KPI formulas in [`docs/KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md) (DEC-03); tests and DQ checks in
> [`docs/TEST_STRATEGY.md`](TEST_STRATEGY.md) (DEC-10); configuration in `config/pipeline.json`.

## 0. Landing (source files in Databricks)

- Unity Catalog Volume **`workspace.bronze.landing`**, path `/Volumes/workspace/bronze/landing/<folder>/`, with `folder` = `bbca`, `bbni`,
  `bmri`, `bbri` (the same layout as the local `data/raw/`).
- Files per folder (DEC-05): `<TICKER>.JK.csv` and `run-summary.json`, **8 files in total**.
- Files are overwritten on re-download (full refresh, DEC-06).

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

**`pipeline_run_id`:** taken from the Job parameter `{{job.run_id}}` (to verify on Free Edition); a UUID when a notebook runs interactively.

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
- **No partitioning or clustering:** about 7,500 daily rows in total (expected: 4 tickers × ~1,886 rows from the base date). *Recorded for REQ-22.*
- **No `dim_date`:** `year` and `month` are columns on the facts.

### Relationships
- Each fact joins `dim_ticker` on `ticker`.
- Facts are **not** joined to each other: one grain per table, one visual group per table.

### Dashboard date windows
- **v1 (MUST):** KPIs are shown for fixed periods (full period, calendar year, month). The global date filter applies to the time-series visuals.
- **SHOULD (attempted in D3 only if time allows):** a Unity Catalog SQL table function such as `gold.fn_window_performance(start_date, end_date)`,
  returning per ticker the window's total return, volatility and max drawdown, called by a parameterized dashboard dataset, so the KPI logic stays in Gold.
  **Unverified on Free Edition** (SQL table functions and AI/BI dashboard parameters). If unavailable, fall back to the MUST approach.

### Rationale
- Each question Q1–Q5 is answered by single-table queries (no fact-to-fact joins), so dashboard queries stay thin (filter and select).
- Each KPI lives in exactly one place, which keeps reconciliation (REQ-16) simple.
- A combined monthly/yearly table with a `period_type` column was **rejected** because it makes queries and key checks harder to read.
