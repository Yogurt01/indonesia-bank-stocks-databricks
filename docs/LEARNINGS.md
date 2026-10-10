# Learnings

> A plain-language glossary of the terms used in this project, and the lessons learned while building it. Every lesson links to the evidence that
> shows it. Run results are owner-reported in `docs/evidence/`.

## 1. Glossary

### Architecture and storage

| Term | Plain explanation | Where in the repo |
| ---- | ----------------- | ----------------- |
| Medallion architecture (Bronze / Silver / Gold) | Three layers of tables with clear jobs: **Bronze** keeps the source data as it arrived, **Silver** cleans and validates it, **Gold** holds business-ready KPIs. Each layer can be rebuilt from the one before it. | `docs/ARCHITECTURE.md`; `notebooks/01_bronze_ingest.py`, `02_silver_transform.py`, `03_gold_build.py` |
| Unity Catalog Volume | A governed folder for files (not tables) inside a Databricks catalog and schema. The source CSVs are uploaded there and read by path. | `workspace.bronze.landing` in `config/pipeline.json`; README step 4 |
| Delta table | The default table format in Databricks: Parquet files plus a transaction log, so every write is atomic and creates a new table version. | All Bronze, Silver, Gold and `ops` tables (`docs/DATA_MODEL.md`) |
| Delta time travel | Reading an older version of a Delta table (`VERSION AS OF n`). Used here to compare the result of one run with the previous one. | `src/bank_pipeline/rerun.py` (`read_version`); `docs/evidence/d2-07-rerun.md` |
| Lineage columns | Columns on every Gold table that say where the data came from: the source run ID, the source ingestion time, the pipeline run ID and the build time. | `gold.with_lineage` in `src/bank_pipeline/gold.py`; `docs/DATA_MODEL.md` |

### Load strategy and reliability

| Term | Plain explanation | Where in the repo |
| ---- | ----------------- | ----------------- |
| Full refresh vs incremental | **Full refresh** rebuilds a table completely from the source on every run; **incremental** processes only new or changed data. This project uses full refresh, because the source republishes its whole history. | DEC-06 in `docs/DECISIONS.md` |
| Idempotent | Running the same job again on the same input leaves the same result: no duplicates and no changed values. | `docs/evidence/d2-07-rerun.md` (9/9 tables identical) |
| Deterministic | Same input, same output, every time; there is no dependence on run order, time or randomness. A deterministic overwrite is what makes the reruns idempotent. | Overwrite writes (`mode("overwrite")`) in `notebooks/01`–`03` |
| Quarantine | A separate table for rows with invalid values. Each row is kept with its original text and a reason code instead of being dropped. | `silver.daily_prices_quarantine`; `silver.reject_reasons` in `src/bank_pipeline/silver.py` |
| `try_cast` and ANSI mode | In ANSI mode (the serverless default), a plain `CAST` of a bad value raises an error and fails the task. `try_cast` returns NULL instead, so the row can be quarantined with a reason. | `silver.parse_bronze` in `src/bank_pipeline/silver.py` |
| CRITICAL / WARN / INFO checks | Severity levels of the data-quality checks. **CRITICAL** stops the task before it writes; **WARN** is recorded but does not block; **INFO** only records a count for monitoring. | `docs/DQ_CATALOG.md`; `src/bank_pipeline/dq.py` |
| Run audit | One row per task and run in `ops.run_audit`, with the start and end time, status, rows in/out/rejected and any error message. | `src/bank_pipeline/audit.py`; `docs/evidence/d2-06-job.md` |
| Reconciliation | Recomputing a value independently (here from Silver) and comparing it with the published value (Gold and the dashboard). | `sql/validation/06_dashboard_reconciliation.sql`; `docs/evidence/d3-03-dashboard-reconciliation.md` |
| `abs_diff` and tolerance | `abs_diff` is the absolute difference between two values. A **tolerance** is the largest difference still accepted as equal, because floating-point results can differ in the last digits (1e-9 for doubles in the rerun check). | `rerun.DOUBLE_TOLERANCE`; the header of `06_dashboard_reconciliation.sql` |

### Finance metrics

| Term | Plain explanation | Where in the repo |
| ---- | ----------------- | ----------------- |
| Base date | The common start date for every bank's index and total return: the first day on which all four banks traded (2019-01-02). | KPI rule G3 in `docs/KPI_DEFINITIONS.md`; `silver.base_date` |
| `adjclose` vs `close` (total vs price return) | `close` is the closing price (here already back-adjusted for corporate actions by the vendor); `adjclose` is additionally adjusted for dividends. A return on `close` is a **price return**; a return on `adjclose` approximates a **total return**. | KPI rule G1 in `docs/KPI_DEFINITIONS.md`; `docs/DATASET.md` §6 |
| Simple return | Today's price divided by the previous price, minus 1. Easy to read and consistent with the normalized index. | KPI K3; `gold.build_daily` |
| Annualized volatility (√252) | The standard deviation of daily returns, scaled to a year by multiplying by √252 (a common count of trading days per year). It measures how much the price moves. | KPI K4/K5; `annualization_factor` in `config/pipeline.json` |
| Drawdown and running peak | The **running peak** is the highest price so far. **Drawdown** is how far today's price is below it (0 or negative). Max drawdown is the deepest such decline. | KPI K6/K7; `gold.build_summary` |
| `zero_all_tickers` / `zero_partial` | Flags for zero-volume rows. `zero_all_tickers`: all four banks show zero volume that day (likely an exchange holiday, inferred). `zero_partial`: one bank shows zero volume while others traded (a vendor gap, inferred). | `silver.add_volume_status`; KPI rule G4 |
| `is_partial` | Marks a month or year that is not complete in the data: the first period (it starts at the base date) or the last one (the snapshot ends before its last weekday). | `gold.build_monthly` / `build_yearly`; `docs/LIMITATIONS.md` |

### Databricks operations

| Term | Plain explanation | Where in the repo |
| ---- | ----------------- | ----------------- |
| Serverless | Compute managed by Databricks: no cluster to configure; it starts on demand. Free Edition offers serverless only. | DEC-07; `docs/evidence/d1-02-workspace-capabilities.md` |
| Cold start | The extra time a run needs when compute has to start from idle. One run after about 9.5 hours idle took 5m41s instead of about 3m40s (likely a cold start, not verified). | `docs/evidence/d2-09-failure-test.md` |
| Lakeflow Job | Databricks' orchestrator: a set of tasks with dependencies, parameters, notifications and run history. | `jobs/indonesia_bank_stocks_pipeline.job.yml` |
| Dynamic value `{{job.run_id}}` | A placeholder that the Job replaces with the current run's ID. Passing it to every task links all the logs and outputs of one run. | Job parameters `pipeline_run_id` and `job_run_id` |
| Git folder | A Databricks workspace folder cloned from a Git repository. The notebooks run directly from the repository code. | README step 2; DEC-09 |
| Repair run | Re-executes only the failed tasks of a Job run and the tasks downstream of them; tasks that succeeded are not rerun. | `docs/RUNBOOK.md` ("Recovery after a failed run") |

## 2. Lessons learned

1. **Design a failure test against the checks you already have.** The first idea, adding a duplicate row, would have been stopped in **Bronze** by the
   row-count check (CSV rows = the source's stated row count), so the Silver duplicate-key stop would never have been tested. The fixture therefore
   **replaces** a row with a copy of the previous one: the count stays the same, Bronze passes, and Silver must stop the run (DEC-13). Result: Silver
   stopped on `silver_no_duplicate_keys` and Gold was skipped (`docs/evidence/d2-09-failure-test.md`).
2. **Check KPI outputs against the data's own flags.** The first K7 rule (the latest date with drawdown 0) reported BBNI's peak on 2019-04-19, a
   zero-volume flat row that carries the previous price. The rule was changed to "the day the peak was set" (DEC-14), and a validation query (G9) now
   confirms that every peak date is a normal trading day (`docs/evidence/d2-05-gold.md`, "DEC-14 rebuild").
3. **Know the platform defaults.** Serverless Job tasks have automatic retries enabled by default: before the change, the Jobs UI task settings showed
   "Immediately, at most 3x (4 total attempts)" (owner-observed, `docs/evidence/d2-06-job.md`). Here a failure is a deterministic data-quality stop, so a retry would fail again and only delay the
   failure email. Retries were disabled on purpose (`disable_auto_optimization: true` in `jobs/indonesia_bank_stocks_pipeline.job.yml`;
   `docs/RUNBOOK.md`, "Why retries are disabled").
4. **The Job parameters panel changes the saved defaults.** Typing a test path into the `catalog` field saved it for every later run; runs
   268776281869222 and 844273765778101 failed in `setup`. The catalog-name validation rejected the value before any SQL ran, so no table changed.
   Tests now use **Run now with different parameters** (one run only) (`docs/evidence/d2-09-failure-test.md`; `docs/RUNBOOK.md`, warning).
5. **Repair run is not always recovery.** After the induced failure, Bronze held the fixture data and `bronze_ingest` had succeeded. Repair run reruns
   only the failed and downstream tasks, so Bronze would have kept the bad data. Recovery was a **new full run** (318690159636842), with KPIs
   identical to before (`docs/evidence/d2-09-failure-test.md`; `docs/RUNBOOK.md`).
6. **Flag, don't delete.** Four rows where one bank shows zero volume on a day the others traded are vendor gaps (inferred). They are kept, flagged
   `zero_partial` and excluded from return statistics, and the WARN check reports them on every run. The gaps they leave in the rolling-volatility
   chart are explained by query R-D6 (only flagged rows, no normal row) instead of looking like missing data (`docs/evidence/d2-03-silver.md`,
   `docs/evidence/d3-03-dashboard-reconciliation.md`).
7. **Floating-point comparisons need a tolerance.** Doubles from grouped aggregations (for example the full-period standard deviation) can differ in
   the last bits between runs, because Spark may combine partial results in a different order. Window functions ordered within a partition are
   typically stable. The rerun check therefore compares doubles within 1e-9, which guards against either case, and everything else exactly
   (`src/bank_pipeline/rerun.py`). In the recovery check, BBNI showed
   an abs_diff of 8.3e-17 only because the recorded reference value was truncated (`docs/evidence/d2-09-failure-test.md`).
8. **Check screenshots and exports before publishing.** All 10 dashboard screenshots were inspected for email addresses, account names, hosts and URLs
   before they were committed, and retaken after the final subtitle edits. The dashboard export was scanned too: it holds Databricks object IDs (not
   credentials), and it was committed unedited by an explicit decision (DEC-16) (`docs/evidence/d3-01-dashboard.md`,
   `docs/evidence/d3-04-clean-state.md`, `docs/evidence/d2-10-config-review.md`).
