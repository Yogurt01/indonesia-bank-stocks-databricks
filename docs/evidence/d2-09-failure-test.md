# D2-09 Induced failure and recovery test (owner-reported)

> Run by the owner on 2026-10-10 following `docs/RUNBOOK.md` (DEC-13 option A). Verification queries: [`sql/validation/05_failure_test.sql`](../../sql/validation/05_failure_test.sql).
> Results are owner-reported; the coding agent has no Databricks access and has not independently verified them. Times are UTC+07.

## 1. Fixture (`notebooks/90_make_failure_fixture`, 01:41)

- 1,887 rows per ticker, matching `run-summary.json`.
- BBCA data row 100 (2019-05-20) was replaced by a copy of the previous row (2019-05-17).
- Duplicated keys: `{'BBCA': ['2019-05-17']}`.
- `landing_path = /Volumes/workspace/bronze/test_fixtures/failure_dup_key`.
- **FIXTURE READY.**

## 2. Misconfiguration observation (not part of the planned test)

- Runs **268776281869222** (01:44) and **844273765778101** (01:45) failed in `setup` after 17s. The fixture path had been entered into the
  **`catalog`** parameter (and saved as the Job default).
- `setup` rejected the invalid catalog name before any SQL ran (catalog identifier validation in `load_config`), the downstream tasks were skipped,
  and no table changed. The setup error text was not captured.
- The Job default parameters were restored before the real test. Lesson recorded in `docs/RUNBOOK.md`.

## 3. Failing run 164942117421206 (01:50, 1m45s)

`landing_path` override = the fixture path; the Job defaults were unchanged.

| Task | Result |
| ---- | ------ |
| `setup` | SUCCEEDED |
| `bronze_ingest` | SUCCEEDED |
| `silver_transform` | **FAILED**: `RuntimeError: Silver CRITICAL checks failed; Silver tables not written: silver_no_duplicate_keys (first duplicated keys=['BBCA@2019-05-17x2'])` |
| `gold_build` | Skipped (upstream failed) |

A failure email was received. Subject: "Error in run 164942117421206 of 'indonesia_bank_stocks_pipeline'"; the message said task `silver_transform` failed
and all downstream tasks were skipped.

### Section 1 queries

| Query | Result |
| ----- | ------ |
| F1 audit | `bronze_ingest` SUCCEEDED, rows 7548/7548/0; `silver_transform` FAILED, rows_in 7548, rows_out NULL, error_message as above; **no `gold_build` row** |
| F2 DQ results | 6 Bronze checks passed. Silver, 14 checks: `silver_no_duplicate_keys` CRITICAL passed = false, failing 1; `silver_same_date_set` WARN false, failing 1 (BBCA 1,886 dates); `silver_zero_partial_count` WARN false, failing 4 (known vendor gaps); `silver_zero_all_tickers_count` INFO 52; all others passed, including `silver_reconciles_with_bronze` (bronze = 7548, silver = 7548, quarantine = 0) |
| F3 Bronze | 1 duplicated key; 4 source files under `/Volumes/workspace/bronze/test_fixtures/` (the fixture-data window) |
| F4 Silver/Gold | `silver.daily_prices` and all 5 Gold tables kept `pipeline_run_id` 371194405323795 (the last good run) with unchanged row counts 7548, 7544, 376, 32, 4, 4 |

## 4. Recovery run 318690159636842 (11:18, 5m41s)

A plain **Run now** with the Job defaults. **Succeeded.**

| Query | Result |
| ----- | ------ |
| R1 audit | 3 SUCCEEDED rows (7548/7548, 7548/7548, 7548/7544) |
| R2 Bronze | 0 duplicated keys, 0 fixture files, 4 real files |
| R3 Gold | `pipeline_run_id` 318690159636842; `total_return` equals the pre-test values: abs_diff 0 for BBCA, BBRI and BMRI; 8.3e-17 for BBNI, because the recorded reference value was truncated |

**Runtime note:** the recovery run took 5m41s, compared with about 3m40s for the earlier runs, on the same data and code. The likely cause is a serverless
cold start after about 9.5 hours idle (not verified).

## What this verifies

- **REQ-12 / ENG-06:**
  - the failure is reported (task error, audit row, DQ results, email);
  - the downstream task is skipped;
  - Gold is not partially overwritten (Silver and Gold keep the last good run);
  - a documented new run recovers the correct state with identical KPIs.
- **REQ-08:** a failed CRITICAL check stops the run before Silver is written; WARN results are recorded without blocking.
- **REQ-11:** the failed run shows the failing task and its error in `ops.run_audit`.
- **REQ-24:** the failure email notification works.
- **Side observation:** the `load_config` catalog validation rejected a misentered parameter before any SQL ran.
