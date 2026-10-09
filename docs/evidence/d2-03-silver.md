# D2-03 Silver transform (owner-reported)

> Run by the owner on 2026-10-10 between about 00:08 and 00:11 (UTC+07): notebook `notebooks/02_silver_transform` run **twice** interactively from
> the Databricks Git folder on serverless compute. Validation queries: [`sql/validation/02_silver.sql`](../../sql/validation/02_silver.sql).
> Results are owner-reported; the coding agent has no Databricks access and has not independently verified them.

## Notebook output

Both runs ended with **SILVER PASS**.

## Validation queries (as reported)

| Query | Result |
| ----- | ------ |
| S1 per-ticker rows and `volume_status` | 1,887 rows per ticker (table below) |
| S2 totals | 7,548 rows = 7,548 distinct (`ticker`, `trade_date`) keys |
| S3 quarantine | 0 rows |
| S4 `zero_partial` rows | 2020-03-13 BBCA (flat at 5560), 2020-03-13 BBNI (flat at 2512.5), 2020-03-16 BBCA (flat at 5560), 2020-03-16 BMRI (flat at 3175); volume 0 |
| S5 base date | **2019-01-02** |
| S6 DQ results | 14 checks: all passed except `silver_zero_partial_count` (WARN, `failing_count = 4`, expected: the known vendor gaps); `silver_zero_all_tickers_count` (INFO) `failing_count = 52` |
| S7 run audit | 2 `SUCCEEDED` rows: `rows_in = rows_out = 7548`, `rows_rejected = 0`; `job_run_id` NULL (interactive runs) |

| ticker | rows | normal | zero_all_tickers | zero_partial |
| ------ | ---: | -----: | ---------------: | -----------: |
| BBCA | 1,887 | 1,872 | 13 | 2 |
| BBNI | 1,887 | 1,873 | 13 | 1 |
| BMRI | 1,887 | 1,873 | 13 | 1 |
| BBRI | 1,887 | 1,874 | 13 | 0 |

## What this verifies

- `ingested_at_utc` with its `+00:00` offset parses to TIMESTAMP via `try_cast` (`silver_source_ingested_at_parsed` passed).
- Every zero-volume row is flat at the previous close (`silver_zero_volume_rows_flat` passed).
- `adjclose` on flat rows equals the previous row's `adjclose` (`silver_flat_rows_adjclose_carried` passed). So K1, K6, K8 and K9 can use all rows
  (rule G5 in `docs/KPI_DEFINITIONS.md`).
- The `volume_status` counts (52 `zero_all_tickers`, 4 `zero_partial`) and the base date (2019-01-02) match the expectations in `docs/KPI_DEFINITIONS.md` §7.
- Silver + quarantine reconciles with Bronze (7,548 = 7,548 + 0); no duplicate keys; the full overwrite is repeatable (two runs).

## Not verified by this run

- Running as a Job task (`job_run_id` was NULL).
- The CRITICAL failure path in Silver; this is covered by the induced-failure test (D2-09, `docs/TEST_STRATEGY.md` §3).
