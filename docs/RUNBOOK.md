# Runbook

> Operational steps for the Databricks Job `indonesia_bank_stocks_pipeline` (definition: `jobs/indonesia_bank_stocks_pipeline.job.yml`) and the
> dashboard "Indonesian Bank Stocks - Performance and Risk". Paths assume the catalog `workspace`. First-time setup: `README.md` ("Reproduce it").

## Normal run

1. In Databricks, open **Jobs & Pipelines → `indonesia_bank_stocks_pipeline` → Run now**. The default parameters use the real landing Volume
   `/Volumes/workspace/bronze/landing`.
2. Expected: the four tasks `setup → bronze_ingest → silver_transform → gold_build` succeed in about 4 minutes on serverless
   (`docs/evidence/d2-06-job.md`; see the cold-start note below).
3. Check:
   - `ops.run_audit`: 3 `SUCCEEDED` rows with `job_run_id = <run id>` (bronze_ingest, silver_transform, gold_build; `setup` writes no audit row).
   - `ops.dq_results` for `pipeline_run_id = <run id>`: no CRITICAL failures. `silver_zero_partial_count` (WARN) is expected to report 4 known vendor
     gaps (`docs/DQ_CATALOG.md`).
   - Optional: `sql/validation/01_bronze.sql`, `02_silver.sql`, `03_gold.sql`.
4. Refresh the dashboard to show the new run (it reads Gold only).

**Cold start.** The first run after a long idle period can take longer: 5m41s after about 9.5 hours idle, against about 3m40s otherwise
(`docs/evidence/d2-09-failure-test.md`; likely a serverless cold start, not verified). This is not an error.

## Rerun / idempotency check

1. Run the Job twice on the same landed files (Normal run, twice).
2. Run `notebooks/91_rerun_check` (read-only). It compares the latest and previous Delta versions of all 9 Bronze/Silver/Gold tables, ignoring
   run-specific columns.
3. Expected: `RERUN CHECK PASS` (9 PASS). Evidence of a passing check: `docs/evidence/d2-07-rerun.md`.
4. A table with no previous version is SKIPPED, which makes the overall result FAIL. A code or rule change between the two runs (as with DEC-14) is
   an intended difference and also shows as FAIL: run the Job twice after deploying a change before using this check.

## Parameters: one-run override vs saved defaults

> **Warning.** Values typed into the Job's **Job parameters** panel change the **saved defaults** for every later run. **Run now with different
> parameters** changes only that one run. In this project, typing the fixture path into the `catalog` field of the parameters panel saved it as the
> default and made runs 268776281869222 and 844273765778101 fail in `setup` (the catalog validation rejected it before any SQL ran;
> `docs/evidence/d2-09-failure-test.md`). Use the one-run override for tests, and check the defaults afterwards.

## Induced failure test

Purpose: prove that a CRITICAL check stops the pipeline before bad data reaches Silver or Gold (DEC-13; executed successfully, see
`docs/evidence/d2-09-failure-test.md`).

1. **Build the fixture:** run `notebooks/90_make_failure_fixture` (defaults: `ticker_folder = bbca`, `row_to_replace = 100`).
   - It copies the 8 landed files to `/Volumes/workspace/bronze/test_fixtures/failure_dup_key/` and replaces one BBCA data row with a copy of the previous
     row.
   - Expected output: `FIXTURE READY`. Row counts are unchanged and exactly 1 duplicated key exists. The real landing Volume is not modified.
2. **Run the Job against the fixture:** Job page → **Run now** dropdown → **Run now with different parameters** →
   `landing_path = /Volumes/workspace/bronze/test_fixtures/failure_dup_key` → **Run**.
3. **Expected:**
   - `bronze_ingest` succeeds and overwrites Bronze with the fixture data.
   - `silver_transform` fails on `silver_no_duplicate_keys` and writes nothing.
   - `gold_build` is skipped (upstream failed).
   - The failure email is sent.
   - Silver and Gold keep the previous good run.
4. **Verify:** run Section 1 of `sql/validation/05_failure_test.sql` with `<failed_run_id>`.
5. **Recover immediately** (next section).

**Window in which Bronze holds fixture data:** from the end of the failing run's `bronze_ingest` until the recovery run's `bronze_ingest` finishes.
- During this window, Silver and Gold still hold the last good run.
- The dashboard reads Gold only, so it is unaffected.
- Running `02_silver_transform` interactively during the window would fail on the same check, by design.

## Recovery after a failed run

1. Fix the cause first. For the induced test, the "fix" is to use the real landing path again.
2. Start a **new full run with the correct parameters**: Job page → **Run now** (check that `landing_path` is back to the default).
3. **Do not use Repair run** for this case. Repair run re-executes only the failed task and its downstream tasks, so `bronze_ingest`, which succeeded,
   is not rerun, and Bronze would still hold the fixture data. Repair run is for transient failures where the earlier tasks' outputs are still
   correct. *(Which parameters a Repair run uses was not verified in this project.)*
4. Verify:
   - all 4 tasks succeed;
   - Section 2 of `sql/validation/05_failure_test.sql` with `<recovery_run_id>`: 3 `SUCCEEDED` audit rows, Bronze without duplicates and back on
     the real files, and Gold with the same KPI values as before.
5. The fixture folder can stay (it lives in its own Volume). To remove it: `dbutils.fs.rm("/Volumes/workspace/bronze/test_fixtures/failure_dup_key", True)`.

## Reset for a clean-state run

Purpose: show that the whole result can be rebuilt from the landed files alone.

1. Run `notebooks/95_reset_environment` with the widget **`confirm = RESET`** (any other value does nothing).
   - It drops every Bronze, Silver, Gold and `ops` table (11 tables, names from `config/pipeline.json`) and prints `RESET DONE`.
   - **It keeps** the schemas and Volumes, so the landing files and test fixtures stay.
   - **Destructive:** the `ops` history (earlier audit rows and DQ results) is deleted as well. This is accepted by design (owner decision
     2026-10-10): the earlier run history is preserved in `docs/evidence/`.
2. Run the Job with its **default parameters** (Normal run). The `setup` task recreates the `ops` tables.
3. Run `sql/validation/01_bronze.sql`, `02_silver.sql`, `03_gold.sql` and `06_dashboard_reconciliation.sql`.
4. Compare with the recorded values, given the same landed snapshot:
   - 4 × 1,887 Bronze and Silver rows, quarantine 0, base date 2019-01-02, 7,544 daily Gold rows;
   - the `ticker_summary` values in `docs/evidence/d2-05-gold.md` and `docs/evidence/d3-03-dashboard-reconciliation.md`.
5. Refresh the dashboard; it must show the same values (`docs/evidence/d3-03-dashboard-reconciliation.md`).

## Why retries are disabled

- The tasks are configured with `disable_auto_optimization: true` and no `max_retries` (`docs/DATA_MODEL.md`, Job section).
- Pipeline failures here are **deterministic**: a failed CRITICAL check sees the same data on a retry and fails again, so an automatic retry only spends
  compute and delays the failure email.
- Transient platform errors are handled manually with **Repair run**, once the cause is understood.

## Dashboard: refresh and re-create

- **Refresh** after every Job run; the dashboard reads Gold only.
- **Re-create** from `dashboards/DASHBOARD_SPEC.md` (datasets in `dashboards/datasets/`), or import an exported `.lvdash.json` if one is available
  (import path to be verified; see the spec, §6).
