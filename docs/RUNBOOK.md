# Runbook

> Operational steps for the Databricks Job `indonesia_bank_stocks_pipeline` (definition: `jobs/indonesia_bank_stocks_pipeline.job.yml`).
> Only the sections needed so far are written here; the remaining ones (environment reset, known failure modes) follow in D3-05.
> Paths assume the catalog `workspace`.

## Normal run

1. In Databricks, open **Jobs & Pipelines → `indonesia_bank_stocks_pipeline` → Run now**. The default parameters use the real landing Volume
   `/Volumes/workspace/bronze/landing`.
2. Expected: the four tasks `setup → bronze_ingest → silver_transform → gold_build` succeed (about 4 minutes on serverless, `docs/evidence/d2-06-job.md`).
3. Check:
   - `ops.run_audit`: 3 `SUCCEEDED` rows with `job_run_id = <run id>` (bronze_ingest, silver_transform, gold_build; `setup` writes no audit row).
   - `ops.dq_results` for `pipeline_run_id = <run id>`: no CRITICAL failures. `silver_zero_partial_count` (WARN) is expected to report 4 known vendor gaps.
   - Optional: `sql/validation/01_bronze.sql`, `02_silver.sql`, `03_gold.sql`.

## Induced failure test

Purpose: prove that a CRITICAL check stops the pipeline before bad data reaches Silver or Gold (D2-09, DEC-13 option A, `docs/TEST_STRATEGY.md` §3).

1. **Build the fixture:** run `notebooks/90_make_failure_fixture` (defaults: `ticker_folder = bbca`, `row_to_replace = 100`).
   - It copies the 8 landed files to `/Volumes/workspace/bronze/test_fixtures/failure_dup_key/` and replaces one BBCA data row with a copy of the previous row.
   - Expected output: `FIXTURE READY`. Row counts are unchanged and exactly 1 duplicated key exists. The real landing Volume is not modified.
> **Warning: one-run override vs saved defaults.** Values typed into the Job's **Job parameters** panel change the **saved defaults** for every
> later run. **Run now with different parameters** changes only that one run. In this project, typing the fixture path into the `catalog` field of
> the parameters panel saved it as the default and made runs 268776281869222 and 844273765778101 fail in `setup`
> (`docs/evidence/d2-09-failure-test.md`). Always use the one-run override for the test, and check the defaults afterwards.

2. **Run the Job against the fixture:** open the Job page → **Run now** dropdown → **Run now with different parameters** → set
   `landing_path = /Volumes/workspace/bronze/test_fixtures/failure_dup_key` → **Run**.
3. **Expected:**
   - `bronze_ingest` **succeeds** and overwrites Bronze with the fixture data.
   - `silver_transform` **fails** on `silver_no_duplicate_keys` and writes nothing.
   - `gold_build` is **skipped** (upstream failed).
   - The failure email is sent.
   - Silver and Gold keep the previous good run.
4. **Verify:** run Section 1 of `sql/validation/05_failure_test.sql` with `<failed_run_id>` = this run's ID, and record the results.
5. **Recover immediately**, as described in the next section.

**Window in which Bronze holds fixture data:** from the end of the failing run's `bronze_ingest` until the recovery run's `bronze_ingest`
finishes.
- During this window, Bronze contains the duplicated row while Silver and Gold still hold the last good run (their `pipeline_run_id` is unchanged).
- The dashboard reads Gold only, so it is unaffected.
- Running `02_silver_transform` interactively during the window would fail on the same CRITICAL check, by design.

## Recovery after a failed run

1. Fix the cause first. For the induced test, the "fix" is simply to use the real landing path again.
2. Start a **new run with the correct parameters**: Job page → **Run now**. The defaults point to the real `landing_path`; if you overrode it before,
   check that it is back to `/Volumes/workspace/bronze/landing`.
3. **Do not use Repair run** for this case. Repair run re-executes only the failed task and its downstream tasks, so `bronze_ingest`, which
   succeeded, is **not** rerun, and Bronze would still hold the fixture data. Recovery therefore needs a **new full run** with the default parameters.
   Repair run is for transient failures (for example a compute hiccup) where the earlier tasks' outputs are still correct.
   *(Which parameters a Repair run uses was not verified in this project.)*
4. Verify:
   - all 4 tasks succeed;
   - Section 2 of `sql/validation/05_failure_test.sql` with `<recovery_run_id>`: 3 `SUCCEEDED` audit rows, Bronze without duplicates and back on
     the real landing files, and Gold rebuilt with the same KPI values as before.
5. The fixture folder can stay (it lives in its own Volume, `test_fixtures`). To remove it: `dbutils.fs.rm("/Volumes/workspace/bronze/test_fixtures/failure_dup_key", True)`.

## Why retries are disabled

- The tasks are configured with `disable_auto_optimization: true` and no `max_retries` (`docs/DATA_MODEL.md`, Job section).
- Pipeline failures here are **deterministic**: a failed CRITICAL DQ check sees the same data on a retry and fails again, so an automatic retry only
  spends compute and delays the failure email.
- Transient platform errors are handled manually with **Repair run**, once the cause is understood.
