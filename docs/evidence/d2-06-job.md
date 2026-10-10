# D2-06 Orchestrated Job run (owner-reported)

> Run by the owner on 2026-10-10. Results are owner-reported; the coding agent has no Databricks access and has not independently verified them.
> Job definition: [`jobs/indonesia_bank_stocks_pipeline.job.yml`](../../jobs/indonesia_bank_stocks_pipeline.job.yml) (sanitized).

## Run

| Item | Value |
| ---- | ----- |
| Job | `indonesia_bank_stocks_pipeline` (job ID 236112722643450) |
| Run ID | 1066568616292788 |
| Trigger | Manual, 2026-10-10 00:50 (UTC+07) |
| Result | **Succeeded** in 3m38s |
| Compute | Serverless, performance optimized |
| Task durations | `setup` 45s → `bronze_ingest` 40s → `silver_transform` 44s → `gold_build` 1m25s |

## Queries (as reported)

| Query | Result |
| ----- | ------ |
| J1 `ops.run_audit` for the run | 3 `SUCCEEDED` rows with `pipeline_run_id = job_run_id = 1066568616292788`: bronze_ingest 7548/7548, silver_transform 7548/7548, gold_build 7548/7544 (rows_in/rows_out) |
| J2 `ops.dq_results` for the run | bronze 6 checks (0 failed), silver 14 (1 failed: `silver_zero_partial_count`, WARN, expected), gold 10 (0 failed) |
| J3 `gold.ticker_summary` | `pipeline_run_id = 1066568616292788` |

## What this verifies

- The four tasks run in dependency order as one Job on serverless compute (REQ-13, ENG-07).
- The `{{job.run_id}}` dynamic value reaches the notebooks on Free Edition, through both the `pipeline_run_id` and the `job_run_id` parameters.
- One `pipeline_run_id` links the audit rows, the DQ results and the Gold lineage of the run.
- **Automatic retries are disabled** (`disable_auto_optimization: true`, no `max_retries`): pipeline failures are deterministic, because a failed
  CRITICAL check fails again on retry. Transient failures are handled with **Repair run**.
  - *Owner-observed (screenshot of the Jobs UI task settings, 2026-10-10, not committed):* before the change, the retry setting of the serverless
    tasks showed the default **"Immediately, at most 3x (4 total attempts)"**. After the change, the exported YAML
    ([`jobs/indonesia_bank_stocks_pipeline.job.yml`](../../jobs/indonesia_bank_stocks_pipeline.job.yml)) shows `disable_auto_optimization: true`
    and no `max_retries` on every task.
- A failure email notification is configured (the owner's address is not recorded here).

## Not verified by this run

- A failed run: the failing task, the downstream tasks skipped, and the failure email. Covered by the induced-failure test (D2-09).
- Scheduled triggering. The Job was launched manually.
