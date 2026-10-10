# D3-07 Demo rehearsal (owner-reported)

> Rehearsed by the owner on 2026-10-11 for a **recorded English video** aimed at a technical audience, following `docs/DEMO_SCRIPT.md`. Results are
> owner-reported; the coding agent has no Databricks access.

## 1. Warm-up Job run **715316575128346**

Run before the rehearsal to avoid a serverless cold start (`docs/DEMO_SCRIPT.md`, "Before recording").

| Item | Value |
| ---- | ----- |
| Result | **Succeeded** in 3m50s |
| Task durations | `setup` 44s → `bronze_ingest` 45s → `silver_transform` 48s → `gold_build` 1m28s |
| Use in the rehearsal | Its run ID was used in the step-4 `ops.dq_results` query |

The 3m50s is slightly longer than the earlier full runs (3m38s–3m43s in `d2-06-job.md` and `d2-07-rerun.md`); together they give a normal range
of 3m38s–3m50s. The 5m41s run after a long idle period (`d2-09-failure-test.md`) remains the only outlier.

## 2. Timed rehearsal

| Step | Content | Time | Cumulative |
| ---: | ------- | ---: | ---------: |
| 1 | Business problem and questions | 0:55 | 0:55 |
| 2 | Architecture | 0:50 | 1:45 |
| 3 | Job run graph | 0:50 | 2:35 |
| 4 | DQ results for the run (SQL) | 1:22 | 3:57 |
| 5 | Rerun evidence | 0:40 | 4:37 |
| 6 | Dashboard walkthrough | 2:25 | 7:02 |
| 7 | Reconciliation query (SQL) | 1:09 | 8:11 |
| 8 | Findings, limitations, next steps | 1:00 | 9:11 |

- Sum of the per-step times: **9:11**.
- One continuous run-through: **9:35**. Target ≤ 10:00: **met**.

## 3. Difficult points

- Presenting SQL results on screen (steps 4 and 7): what to point at in the result grid.
- The dashboard click path (step 6): the order of visuals, setting and resetting the ticker filter.

## 4. Changes applied to the script after the rehearsal

Owner-approved, in `docs/DEMO_SCRIPT.md`:
- recorded-video wording in the introduction; the Job is not triggered on camera, while the SQL queries in steps 4 and 7 are run on camera;
- a greeting in step 1 and a closing line in step 8;
- step 4: point to the row count (30) and the single WARN row; say the per-layer counts (6/14/10);
- step 5: "Instead of rerunning the Job in this video";
- the backup section marked optional for a recorded video;
- a new likely question 6 (batch vs streaming) and a "Recording tips" section.

## What this verifies

- **Demonstration readiness:** the script runs within the 10-minute target (9:35 continuous) on a warm workspace, using a fresh successful Job run.
- **Not verified here:** the final video. Its recording and the README link are still pending.
