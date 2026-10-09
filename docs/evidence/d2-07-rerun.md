# D2-07 Rerun / idempotency test (owner-reported)

> Run by the owner on 2026-10-10. Method: `docs/TEST_STRATEGY.md` §3 (run the Job twice on the same input, then `notebooks/91_rerun_check`).
> Results are owner-reported; the coding agent has no Databricks access and has not independently verified them.

## The two Job runs (same landed input)

| Job run ID | Started (UTC+07) | Duration | Result |
| ---------- | ---------------- | -------- | ------ |
| 1066568616292788 | 2026-10-10 00:50 | 3m39s | Succeeded |
| 371194405323795 | 2026-10-10 01:15 | 3m43s | Succeeded |

The `gold_build` rows in `ops.run_audit` have `pipeline_run_id = job_run_id` = 371194405323795 and 1066568616292788, both `SUCCEEDED`.

## Rerun check result

`notebooks/91_rerun_check` compared **Delta version 2 with version 3** of all 9 tables. Every compared operation is "CREATE OR REPLACE TABLE AS SELECT":
versions 0–1 are the two interactive runs and versions 2–3 are the two Job runs, with no maintenance versions in between.

| Table | rows_prev = rows_latest | dup_keys | missing_rows | mismatched_non_double | Result |
| ----- | ----------------------: | -------: | -----------: | --------------------: | ------ |
| bronze.daily_prices_raw | 7,548 | 0 | 0 | 0 | PASS |
| bronze.source_run_summary | 4 | 0 | 0 | 0 | PASS |
| silver.daily_prices | 7,548 | 0 | 0 | 0 | PASS |
| silver.daily_prices_quarantine | 0 | — | — | — | PASS (count-only comparison) |
| gold.dim_ticker | 4 | 0 | 0 | 0 | PASS |
| gold.fact_daily_metrics | 7,544 | 0 | 0 | 0 | PASS |
| gold.fact_monthly_metrics | 376 | 0 | 0 | 0 | PASS |
| gold.fact_yearly_metrics | 32 | 0 | 0 | 0 | PASS |
| gold.ticker_summary | 4 | 0 | 0 | 0 | PASS |

`max_double_diff` was within the 1e-9 tolerance for every keyed table. The exact values were not captured in the screenshot.

**RERUN CHECK PASS** (9 PASS, 0 FAIL, 0 SKIPPED).

## What this verifies

- REQ-09 / ENG-02: running the full Job twice on the same input gives identical row counts in every layer, identical non-double values, Gold KPI
  doubles within 1e-9, and 0 duplicate keys. The mechanism is a deterministic full overwrite (DEC-06).
- The comparison is between two **different** Job runs (versions 2 and 3, linked by the two `gold_build` run IDs), not a run compared with itself.
