# Demo Script (≤ 10 minutes)

> A recorded video walkthrough of the project in eight steps, with a time budget per step. The Job is not triggered on camera: the demo shows a recent
> successful run and recorded evidence. The SQL queries in steps 4 and 7 are run on camera (pre-run once to warm the warehouse). Times in brackets are
> cumulative. Paths assume the catalog `workspace`. Rehearsal (2026-10-11): 9:35 in one continuous run (`docs/evidence/d3-07-demo-rehearsal.md`).

## Before recording (15–20 minutes ahead)

- [ ] **Warm up compute:** run the Job once, about 15 minutes before (serverless cold start can add about 2 minutes: 5m41s vs about 3m40s,
      `docs/evidence/d2-09-failure-test.md`). Note its **run ID** for step 4. Run one query in the SQL editor so the SQL warehouse is warm.
- [ ] **Job defaults are correct:** Job → parameters show `catalog = workspace` and `landing_path = /Volumes/workspace/bronze/landing` (no fixture
      override left over; see the warning in `docs/RUNBOOK.md`).
- [ ] **Open tabs, in this order:**
  1. the GitHub README;
  2. `docs/ARCHITECTURE.md`;
  3. the Job page (latest run graph);
  4. a SQL editor tab with the step-4 queries;
  5. `docs/evidence/d2-07-rerun.md`;
  6. the dashboard (published view, no filter);
  7. a SQL editor tab with R-D1 from `sql/validation/06_dashboard_reconciliation.sql`;
  8. `docs/REPORT.md` §8.
- [ ] Dashboard filters reset (Ticker = All, no date range). The dashboard has been refreshed after the warm-up run.
- [ ] The backup files below are available offline.

## Steps

| # | Time | Where | Show | Say |
| - | ---- | ----- | ---- | --- |
| 1 | 0:45 (0:45) | README, "Business questions" | Q1–Q5 and the one-paragraph summary | "Hi, I'm [name]. In this video I'll walk you through an end-to-end batch data-engineering project on Databricks Free Edition. An investment analyst wants a like-for-like, descriptive comparison of four Indonesian bank stocks. The questions are total return, volatility, drawdown, monthly and yearly returns, and volume. This is historical analysis, not advice." |
| 2 | 1:00 (1:45) | `docs/ARCHITECTURE.md`, Mermaid diagram | Kaggle CSV → Volume → Bronze → Silver (+ quarantine) → Gold → dashboard; `ops` audit and DQ tables; the 4-task Job | "Bronze keeps every source value as text, Silver types and validates it, and Gold holds the KPIs at one grain per table. Every task records an audit row and its data-quality results, and the dashboard reads Gold only." |
| 3 | 1:00 (2:45) | Jobs & Pipelines → `indonesia_bank_stocks_pipeline` → latest run | The run graph: `setup → bronze_ingest → silver_transform → gold_build`, all green, with durations | "This is a batch Job on serverless compute. One run ID is passed to every task, so all the logs, checks and Gold lineage of a run are linked. Retries are off on purpose, because a data-quality failure is deterministic." |
| 4 | 1:30 (4:15) | SQL editor | `SELECT layer, check_name, severity, passed, failing_count, details FROM workspace.ops.dq_results WHERE pipeline_run_id = '<run id>' ORDER BY layer, severity, check_name;`, then query S4 from `sql/validation/02_silver.sql` (the 4 `zero_partial` rows). Point to the row count (30) and the single WARN row; state the per-layer counts (6/14/10) verbally. *(The rehearsal used warm-up run 715316575128346.)* | "30 checks ran: 6 in Bronze, 14 in Silver and 10 in Gold. The only non-passing one is a WARN: 4 rows where one bank shows zero volume on a day the others traded, which are vendor gaps. We flag them and exclude them from return statistics, but we never delete them, and a CRITICAL failure would have stopped the run before writing." |
| 5 | 0:45 (5:00) | `docs/evidence/d2-07-rerun.md` | The result table: 9/9 tables PASS, versions 2 vs 3 | "Instead of rerunning the Job in this video: two Job runs on the same input were compared table by table with Delta time travel. Every table was identical, with no duplicates and doubles within 1e-9, because each task does a deterministic full overwrite." |
| 6 | 2:30 (7:30) | Dashboard | V1 summary table and V2 total-return bar; V3 normalized index; set **Ticker = BBCA**, then V4 rolling volatility and V6 drawdown; V7 yearly returns (partial years labeled) | "BMRI has the highest total return since 2019-01-02 and BBCA the lowest volatility. With BBCA selected, you can see its deepest drawdown is the recent 2024–2026 episode, not 2020. The summary KPIs are full-period values; the date filters only change the time-series charts, and the chart subtitles say so." |
| 7 | 1:00 (8:30) | SQL editor, R-D1 | R-D1 recomputes total return from **Silver** and shows the Gold value and `abs_diff` | "This query does not touch Gold's KPI logic: it recomputes total return from the cleaned prices. BBCA is 0.4097, which is 40.97% on the dashboard, and abs_diff is 0. All 14 checked values match." |
| 8 | 1:00 (9:30) | `docs/REPORT.md` §8–§10 | Findings table; the price-vs-total-return observation; limitations; next steps | "Findings are descriptive for one snapshot. The price basis matters: on closing prices, two of the four banks are down since 2019, while on total return all are up. Limitations include vendor-adjusted prices and a single snapshot; next steps are window KPIs, snapshot history and deployment as code. Thanks for watching. All the docs and evidence are linked in the README." |

Buffer: 0:30 for questions or a slow page load.

## Backup (optional for a recorded video: re-record instead)

| Step | Show instead |
| ---- | ------------ |
| 3 | `docs/evidence/d2-06-job.md` (run 1066568616292788, task durations) and `docs/evidence/d3-04-clean-state.md` (run 994907076175214) |
| 4 | `docs/DQ_CATALOG.md` and `docs/evidence/d2-03-silver.md` (S4 rows, the WARN of 4) |
| 5 | `docs/evidence/d2-07-rerun.md` |
| 5b (failure) | `docs/evidence/d2-09-failure-test.md` (failing run 164942117421206, recovery run 318690159636842) |
| 6 | Screenshots `docs/evidence/dashboard/01-unfiltered-overview.png` … `05-…`, BBCA views `06-…` … `10-…` |
| 7 | `docs/evidence/d3-03-dashboard-reconciliation.md` |
| 8 | `docs/REPORT.md` |

## Likely questions (short answers)

1. **Why full refresh instead of incremental?** The source republishes its entire history every day, and adjusted prices change retroactively, so
   appending would mix inconsistent histories. At 4 × 1,887 rows a deterministic overwrite is cheap and idempotent by construction (DEC-06; proven in
   `d2-07-rerun.md`).
2. **Why hand-written DQ checks instead of declarative pipelines?** I needed explicit control: a per-run audit row, quarantine with reason codes, blocking
   before write, and a CRITICAL/WARN/INFO split recorded in a queryable table. For a small full-refresh batch, the extra abstraction added risk without
   benefit (DEC-05).
3. **How do you prove idempotency?** Two Job runs on the same input, then a notebook compares the latest and previous Delta versions of all 9 tables:
   counts, key uniqueness, a full outer join on the key, exact equality for non-doubles and 1e-9 for doubles. Result 9/9 PASS. A clean-state rebuild from
   empty tables also reproduced identical results.
4. **How is a failure contained?** Every task runs its checks before writing. In the induced test a duplicated key passed Bronze, Silver raised before
   writing, Gold was skipped by the Job, and Silver and Gold kept the last good run, which is what the dashboard reads. Recovery is a new full run, not Repair run, because
   Repair would not rerun the Bronze task that loaded the bad data.
5. **Why `adjclose`?** It includes dividends and corporate actions, so banks with different dividend policies are compared fairly. On closing prices
   alone, BBNI and BBRI show a price decline since 2019 (−22.5% and −8.9% from the profiled close values), while their total returns are positive.
6. **Why batch, not streaming?** The source is a daily full-history snapshot, not an event stream, and the questions are historical, so they need no
   low-latency freshness. Batch is the simplest reliable option (DEC-04). Scheduling the Job is a possible future improvement; it is not implemented
   (the Job is triggered manually).

Longer, evidence-linked answers: `docs/INTERVIEW_QA.md`.

## Recording tips

- Record the steps separately and join them afterwards if needed; a mistake then costs one step, not the whole take.
- Zoom the browser so that table values and SQL results are readable in the video.
- Reset the dashboard filters (Ticker = All, no date range) between takes.
- Run the warm-up Job and one SQL query before recording, so neither the Job page nor the SQL editor waits for compute on camera.
- Check that no email address or account information is visible in any frame (browser profile icons, workspace menus, notification pop-ups) before
  publishing.
