# D1-11 Landing smoke test (owner-reported)

> Run by the owner on 2026-10-09 at about 23:31 (UTC+07): notebook `notebooks/10_landing_smoke_test` from the Databricks Git folder on
> serverless compute, after uploading the 8 files (DEC-05) to `/Volumes/workspace/bronze/landing/<folder>/`. Results are owner-reported;
> the coding agent has not independently verified them. The notebook is read-only and writes no table.

## Result table (as reported)

| ticker | csv_exists | json_exists | header_ok | csv_rows | json_daily_rows | rows_match | json_ticker | date_min | date_max |
| ------ | ---------- | ----------- | --------- | -------: | --------------: | ---------- | ----------- | -------- | -------- |
| BBCA | true | true | true | 1887 | 1887 | true | BBCA.JK | 2019-01-01 | 2026-10-08 |
| BBNI | true | true | true | 1887 | 1887 | true | BBNI.JK | 2019-01-01 | 2026-10-08 |
| BMRI | true | true | true | 1887 | 1887 | true | BMRI.JK | 2019-01-01 | 2026-10-08 |
| BBRI | true | true | true | 1887 | 1887 | true | BBRI.JK | 2019-01-01 | 2026-10-08 |

Distinct source run_ids: `{20261009T124332+0700}`. **SMOKE TEST PASS.**

## run-summary.json schema (reported identical for all four)

```
root
 |-- intervals: struct
 |    |-- 1d:  struct (date_max: string, duplicate_dates: long, rows: long)
 |    |-- 1mo: struct (date_max: string, duplicate_dates: long, rows: long)
 |    |-- 1wk: struct (date_max: string, duplicate_dates: long, rows: long)
 |-- run_id: string
 |-- stock: string
 |-- ticker: string        (source symbol, for example BBCA.JK)
```

`date_max` is a string formatted `YYYY-MM-DD HH:MM:SS`.

## Notes

- The "[Truncated to first 4096 bytes]" line in the output is the default notice of `dbutils.fs.head`. The JSON files are about 420 bytes, so
  nothing relevant was cut, and the header check reads only the first line.
- **What this verifies:** all 8 landed files exist; the CSV headers match `source_columns` exactly; the row counts match the source's own
  `run-summary.json` and the local profile in `docs/DATASET.md` (1,887 per ticker); the date range is 2019-01-01 → 2026-10-08; there is one shared
  source run_id. This completes the Databricks read of the real daily CSVs (D1-04).
