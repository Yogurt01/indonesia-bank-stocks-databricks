# D3-03 Dashboard reconciliation (owner-reported)

> Dashboard values as displayed in "Indonesian Bank Stocks - Performance and Risk" (`docs/evidence/d3-01-dashboard.md`). Query values come from
> `sql/validation/06_dashboard_reconciliation.sql`, run by the owner on 2026-10-10 at about 20:05 (UTC+07). Each query recomputes the KPI
> independently from `silver.daily_prices` and shows the Gold value and `abs_diff`. Owner-reported; the coding agent has no Databricks access.
> Covers REQ-16 / DASH-06.

**Match rule:** the dashboard shows percentages with 2 decimals, so a value matches when the query value, rounded the same way, equals the dashboard value,
**and** `abs_diff` (Silver vs Gold) is within the tolerance stated in the SQL file (1e-12; 1e-9 for volatility).

| KPI | Filter context | Dashboard value | Query (file/ID) | Query value (Silver) | Gold value | abs_diff | Match |
| --- | -------------- | --------------: | --------------- | -------------------: | ---------- | -------: | ----- |
| Total return BBCA (V1/V2) | No filter (full period) | 40.97% | `06_dashboard_reconciliation.sql` R-D1 | 0.4096571841753591 | same | 0 | ✅ |
| Total return BBNI (V1/V2) | No filter (full period) | 9.50% | R-D1 | 0.09495904573019698 | same | 0 | ✅ |
| Total return BBRI (V1/V2) | No filter (full period) | 43.02% | R-D1 | 0.4301591927421744 | same | 0 | ✅ |
| Total return BMRI (V1/V2) | No filter (full period) | 75.97% | R-D1 | 0.7596948888403188 | same | 0 | ✅ |
| Max drawdown BBCA (V1) | No filter | −51.79% | R-D2 | −0.5179204835090025 | same | 0 | ✅ |
| Max drawdown BBNI (V1) | No filter | −66.16% | R-D2 | −0.6615630803271564 | same | 0 | ✅ |
| Max drawdown BBRI (V1) | No filter | −52.43% | R-D2 | −0.5243351988752678 | same | 0 | ✅ |
| Max drawdown BMRI (V1) | No filter | −52.05% | R-D2 | −0.5205072369380116 | same | 0 | ✅ |
| Volatility (ann.) BBCA (V1/V5) | No filter | 26.22% | R-D3 | 0.2622313492568432 | same | 0 | ✅ |
| Volatility (ann.) BBNI (V1/V5) | No filter | 34.15% | R-D3 | 0.3414590613143148 | same | 0 | ✅ |
| Volatility (ann.) BBRI (V1/V5) | No filter | 32.62% | R-D3 | 0.32618778401758614 | same | 0 | ✅ |
| Volatility (ann.) BMRI (V1/V5) | No filter | 33.51% | R-D3 | 0.3350570398009743 | same | 0 | ✅ |
| Yearly return BBCA 2022 (V7) | Ticker = BBCA (filtered view) | 19.38% | R-D4 | 0.19382545548113872 | same | 0 | ✅ |
| Monthly return BMRI 2020-03 (V8) | Ticker = BMRI; month range includes 2020-03 | −35.67% | R-D5 | −0.3567009363501291 | identical digits shown | not visible ¹ | ✅ |

¹ The `abs_diff` column was cut off in the screenshot. The Silver and Gold values shown have identical digits, recorded as "identical values shown".

**Result: all 14 rows match at display precision and within tolerance.**

## R-D6 (owner-added): where `vol_60d_ann` is NULL after the warm-up

Query R-D6 in `sql/validation/06_dashboard_reconciliation.sql` lists the rows of `gold.fact_daily_metrics` where `vol_60d_ann` is NULL **after** each
ticker's first non-NULL value. The owner reported:

| volume_status | BBCA | BBNI | BBRI | BMRI | Dates |
| ------------- | ---: | ---: | ---: | ---: | ----- |
| `zero_all_tickers` | 10 | 10 | 10 | 10 | 2019-04-03 … 2019-06-07 |
| `zero_partial` | 2 | 1 | 0 | 1 | BBCA 2020-03-13, 2020-03-16; BBNI 2020-03-13; BMRI 2020-03-16 |
| `normal` | 0 | 0 | 0 | 0 | — |

**Explanation.** There are 13 `zero_all_tickers` dates. 2019-01-01 precedes the base date, and 2019-02-05 and 2019-03-07 fall inside the 60-session
warm-up, which leaves 10 after it. Flagged rows have NULL return statistics by design (KPI rule G5), so these are the gaps visible in V4. No normal
trading row is missing a volatility value.
