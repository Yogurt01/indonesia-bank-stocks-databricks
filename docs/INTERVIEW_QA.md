# Interview Q&A

> Likely interview questions about this project, with short answers grounded in the recorded evidence (`docs/evidence/`, owner-reported runs).
> Glossary and lessons: `docs/LEARNINGS.md`. Demo: `docs/DEMO_SCRIPT.md`.

## Design

**1. Why full refresh instead of incremental?**
Correctness first. The source re-extracts the **full history** on every refresh (`mode: full`), and `adjclose` is rewritten retroactively whenever a
dividend or corporate action is applied. Appending new rows would therefore mix prices adjusted on different bases into one inconsistent history
([`DATASET.md`](DATASET.md) §6, DEC-06). Size is the secondary reason: 4 × 1,887 rows make a deterministic overwrite cheap. The rerun test confirms
the result is idempotent: 9/9 tables identical ([`d2-07-rerun.md`](evidence/d2-07-rerun.md)).

**2. Why batch, not streaming?**
The source is a daily full-history snapshot, not an event stream, and the business questions are historical, so there is no need for low-latency
freshness. Batch is the simplest reliable option (DEC-04 in [`DECISIONS.md`](DECISIONS.md)). Scheduling the Job is a possible future improvement; it is
not implemented, and the Job is triggered manually.

**3. Why hand-written data-quality checks instead of a declarative pipeline?**
I needed four explicit controls: a **per-run audit row** for every task (status, rows in/out/rejected, error), a **quarantine** table with reason codes,
**blocking before write** when a CRITICAL check fails, and every check's result (CRITICAL, WARN or INFO) recorded in the queryable `ops.dq_results`
table. Plain notebook code gives direct control over all four. For a small full-refresh batch, a declarative pipeline would add abstraction without
benefit (DEC-05; [`DQ_CATALOG.md`](DQ_CATALOG.md)).

**4. Why `adjclose` and not `close`?**
`adjclose` also includes dividends, so banks with different dividend policies are compared fairly on total return. The basis changes the picture: on
the profiled `close` values, BBNI is −22.5% and BBRI −8.9% from 2019-01-01 to 2026-10-08, while their total returns since 2019-01-02 are +9.50% and
+43.02% ([`REPORT.md`](REPORT.md) §8; the `close` figures are computed from [`DATASET.md`](DATASET.md) §5 and are not a pipeline KPI). The vendor's
adjustment method is inferred, not documented.

**5. Why is the base date 2019-01-02?**
The base date is the first day on which **all four** banks traded (KPI rule G3), and it is computed by a query, not hard-coded. 2019-01-01 is a
zero-volume flat row for all four banks (likely an exchange holiday, inferred), so starting there would base the index on a non-traded price. The
computed value 2019-01-02 was verified in Silver ([`d2-03-silver.md`](evidence/d2-03-silver.md), S5).

**6. Why are zero-volume rows excluded from return statistics?**
They are flat rows that carry the previous price, so counting them as 0% returns would artificially lower volatility and dilute averages. They get NULL
return statistics instead, and the price move across the gap is captured on the next traded day (KPI rule G5 in
[`KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md)). They are never deleted: levels and drawdown still use them, and query R-D6 shows that NULL volatility after
the warm-up occurs only on flagged rows ([`d3-03-dashboard-reconciliation.md`](evidence/d3-03-dashboard-reconciliation.md)).

## Reliability

**7. How do you prove idempotency?**
Two Job runs on the same input (1066568616292788 and 371194405323795), then `notebooks/91_rerun_check` compares the latest and previous **Delta
versions** (time travel, versions 2 vs 3) of all 9 tables. For each table it checks row counts and key uniqueness, then does a **full outer join on
the key**: non-double columns must be exactly equal, and doubles within 1e-9. Only run-specific columns are excluded (`pipeline_run_id`,
`bronze_pipeline_run_id`, `bronze_loaded_at`, `processed_at`, `quarantined_at`, `built_at`; see `src/bank_pipeline/rerun.py`), while the source
lineage columns are compared. The result was **identical** for 9/9 tables ([`d2-07-rerun.md`](evidence/d2-07-rerun.md)), and a rebuild from empty
tables (run 994907076175214) reproduced the same counts and KPIs ([`d3-04-clean-state.md`](evidence/d3-04-clean-state.md)).

**8. How is a failure contained and recovered?**
In the induced test, one BBCA row was replaced by a copy of the previous row (DEC-13). Bronze passed, because the row count was unchanged. Silver
**stopped before writing** on `silver_no_duplicate_keys` (CRITICAL), Gold was **skipped** by the Job, and the failure email arrived. Silver and Gold kept
the last good run, and the dashboard reads Gold only (it was built after this test). Recovery was a **new full run** (318690159636842), not Repair run:
Repair reruns only the failed and downstream tasks, so Bronze would have kept the fixture data. KPIs were identical after recovery
([`d2-09-failure-test.md`](evidence/d2-09-failure-test.md), [`RUNBOOK.md`](RUNBOOK.md)).

**9. Quarantine or stop: how do you decide?**
**Quarantine** is for row-level invalid values (a bad date, a non-positive price, inconsistent OHLC): the problem is isolated, so the row is kept with
its original text and a reason code, and the pipeline continues. A **duplicate key** means two rows claim the same ticker and date, so the snapshot
itself is broken and neither row can be trusted: the run stops (CRITICAL) ([`ARCHITECTURE.md`](ARCHITECTURE.md), [`DQ_CATALOG.md`](DQ_CATALOG.md)).

**10. How do you know the dashboard values are correct?**
The dashboard datasets are thin selects over Gold, with no custom calculations. The reconciliation queries R-D1 to R-D5 recompute each KPI
**independently from Silver** and show the Gold value and `abs_diff` next to it. All **14/14** checked values match: total return, max drawdown and
volatility for the four banks, one yearly and one monthly return, with abs_diff 0 ([`d3-03-dashboard-reconciliation.md`](evidence/d3-03-dashboard-reconciliation.md)).
R-D6 explains the gaps in the volatility chart.

## Reflection

**11. What was hardest, or what went wrong?**
Three things. The first failure-test design would have been stopped by the Bronze row-count check, so it would never have reached Silver (DEC-13). The
first peak-date rule picked a flat non-trading row for BBNI and had to be corrected (DEC-14). And typing a test value into the Job parameters panel
silently changed the saved default, which made two runs fail in `setup` (caught by the catalog validation before any SQL ran). Details and evidence:
[`LEARNINGS.md`](LEARNINGS.md) §2.

**12. What would you do next?**
Window KPIs over any dashboard date range (a SQL table function in Gold), snapshot history instead of overwrite, deployment as code with Databricks
Asset Bundles, CI running the plain-Python tests, a scheduled Job, verification of corporate actions against an official source, and alerts on WARN
trends from `ops.dq_results` ([`REPORT.md`](REPORT.md) §10).
