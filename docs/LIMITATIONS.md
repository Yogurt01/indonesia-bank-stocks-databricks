# Known Limitations

> What this project does not do, or does only approximately. Each item names its source. The analysis is descriptive and historical,
> **not investment advice**.

## Data

- **No as-traded prices.** The source provides prices back-adjusted for corporate actions (`close`) and additionally for dividends (`adjclose`).
  The vendor's adjustment method is inferred, not documented (`docs/DATASET.md` §6).
- **`adjclose` is rewritten on every source refresh.** Each source version re-extracts the full history, and the pipeline does a full refresh
  (DEC-06). KPI values therefore belong to a snapshot (here, source run `20261009T124332+0700`, last trade date 2026-10-08), and no history across
  snapshots is kept.
- **Float32 source precision.** All prices are float32 values stored as double (`docs/DATASET.md` §4). The KPIs are ratios, so this is immaterial at
  the displayed precision.
- **Volume may not be adjusted for corporate actions.** This is inferred only and was not checked. If true, monthly volume levels (V9) may shift
  around the BBNI (~2023-10-05) and BMRI (~2023-04-03) adjustment dates. Compare each bank with itself over time.
- **Vendor gaps are flagged, not repaired.** BBCA 2020-03-13 and 2020-03-16, BBNI 2020-03-13 and BMRI 2020-03-16 are zero-volume flat rows on days
  when the other banks traded (`zero_partial`). They are excluded from return statistics, not filled.
- **Single ticker per bank, no fundamentals.** There is no market capitalization, valuation, shares outstanding or index benchmark.
- **Upstream licence unverified.** Kaggle labels the datasets `world-bank`, but the data originates from Yahoo Finance, whose redistribution terms
  were not verified. The raw data is therefore **not redistributed** in this repository; download it yourself (`README.md`).

## Metric conventions

- **Annualization uses √252,** a market convention. The observed sessions per year are about 236–247, so annualized volatility is slightly higher than
  an observed-sessions factor would give. The same factor applies to every bank, so rankings are unaffected.
- **Relative volume (K10) uses a 60-session mean,** so it is sensitive to volume spikes. It is computed in Gold but not shown on the dashboard.
- **`is_partial` is conservative.** A period is flagged as partial when the snapshot ends before its last weekday, so an exchange holiday on that weekday
  would mark a complete period as partial.
- **Dashboard KPIs are full-period values.** The summary (V1, V2, V5) and yearly returns (V7) do not change with the date filters; window KPIs over an
  arbitrary date range are not implemented in v1.
- **Total return since the base date 2019-01-02,** the first day on which all four banks traded; the index (V3) is not rebased to the filter start.

## Platform and operations

- **Databricks Free Edition** (`docs/evidence/d1-02-workspace-capabilities.md`):
  - serverless compute only;
  - usage quotas (compute can be shut down for the rest of the day if exceeded);
  - at most 5 concurrent job tasks;
  - non-commercial use, no SLA;
  - quotas were not measured.
- **Runtime varies.** Job runs took 3m38s–3m43s, and 5m41s after about 9.5 h idle (likely a serverless cold start, not verified;
  `docs/evidence/d2-09-failure-test.md`).
- **Gold writes are atomic per table, not across the five tables.** A failure between table writes can leave tables from different runs until the task
  is rerun (`docs/RUNBOOK.md`).
- **Single environment.** There is no separate development, test or production; the Job definition in `jobs/` is recreated by hand (no Asset Bundles).
- **Manual data refresh.** Downloading from Kaggle and uploading to the Volume are manual steps; the Job itself is triggered manually.
