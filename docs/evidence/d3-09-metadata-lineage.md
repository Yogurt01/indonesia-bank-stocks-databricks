# D3-09 Gold metadata and lineage (REQ-25): template, not yet run

> **Status: pending.** The code that applies the Gold table and column comments (`src/bank_pipeline/comments.py`, called by
> `notebooks/03_gold_build.py`) has not yet run in Databricks. Fill in the sections below from the owner's results; do not edit the expected
> values. Procedure: `docs/RUNBOOK.md` ("Metadata: comments and lineage"). Queries: [`sql/validation/07_metadata.sql`](../../sql/validation/07_metadata.sql).

## 1. Job run with the comment step

| Item | Value |
| ---- | ----- |
| Job run ID | _to be filled_ |
| Result and duration | _to be filled_ |
| `gold_build` output line | Expected: `Applied 53 comment statements to the Gold tables`. Observed: _to be filled_ |
| DQ checks for the run | Expected: unchanged, 30 (Bronze 6, Silver 14, Gold 10), only the known WARN `silver_zero_partial_count`. Observed: _to be filled_ |

## 2. Table comments (M1)

| Table | Comment present (expected: yes) |
| ----- | ------------------------------- |
| `dim_ticker` | _to be filled_ |
| `fact_daily_metrics` | _to be filled_ |
| `fact_monthly_metrics` | _to be filled_ |
| `fact_yearly_metrics` | _to be filled_ |
| `ticker_summary` | _to be filled_ |

## 3. Column comments (M2)

| Table | Expected n_columns / n_commented | Observed |
| ----- | -------------------------------- | -------- |
| `dim_ticker` | 7 / 5 | _to be filled_ |
| `fact_daily_metrics` | 18 / 13 | _to be filled_ |
| `fact_monthly_metrics` | 11 / 9 | _to be filled_ |
| `fact_yearly_metrics` | 9 / 8 | _to be filled_ |
| `ticker_summary` | 13 / 13 | _to be filled_ |

## 4. Lineage graph of `gold.ticker_summary`

- Path: Catalog Explorer → `workspace` → `gold` → `ticker_summary` → **Lineage** tab → lineage graph.
- Expected upstream tables: `silver.daily_prices`, then `bronze.daily_prices_raw` and `bronze.source_run_summary`.
- Observed: _to be filled_.
- Screenshot: _to be added_ (for example `docs/evidence/metadata/ticker-summary-lineage.png`; check it for email addresses, account names, hosts
  and URLs before committing).

## 5. Rerun check after the change (optional)

The comment statements add metadata-only Delta versions after every build, which `notebooks/91_rerun_check` is set to skip (`SET TBLPROPERTIES`,
`CHANGE COLUMN`). Expected operation names, unverified: record here the operations shown by `DESCRIBE HISTORY workspace.gold.ticker_summary`
after one build, and, if the rerun check is run, that it compared two `CREATE OR REPLACE TABLE AS SELECT` versions.

- `DESCRIBE HISTORY` operations after one build: _to be filled_
- Rerun check result and compared operations: _to be filled_

## What this will verify

- REQ-25: the Gold tables and their key and KPI columns carry comments, and lineage is viewable in Unity Catalog, with a screenshot.
