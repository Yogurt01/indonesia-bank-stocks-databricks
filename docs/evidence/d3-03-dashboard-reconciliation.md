# D3-03 Dashboard reconciliation (template, to be filled)

> **Status: template, no values yet.** Fill it from the finished dashboard (screenshots in `docs/evidence/dashboard/`) and from the results of
> `sql/validation/06_dashboard_reconciliation.sql`. Do not enter any value that was not read from a real screenshot or query result.
> REQ-16 / DASH-06: every headline KPI, plus at least one filtered view, must match.

**Match rule:** the dashboard shows percentages with 2 decimals, so a value matches when the query value, rounded the same way, equals the dashboard value
(for example a query value of 0.4096571841753591 matches a displayed 40.97%). The query result also shows the Gold value and `abs_diff`; an `abs_diff`
above the tolerance stated in the SQL file is a mismatch even if the rounded display agrees.

| KPI | Filter context | Dashboard value | Query (file/ID) | Query value | Match |
| --- | -------------- | --------------- | --------------- | ----------- | ----- |
| Total return BBCA (V1/V2) | No filter (full period) | | `06_dashboard_reconciliation.sql` R-D1 | | |
| Total return BBNI (V1/V2) | No filter (full period) | | R-D1 | | |
| Total return BBRI (V1/V2) | No filter (full period) | | R-D1 | | |
| Total return BMRI (V1/V2) | No filter (full period) | | R-D1 | | |
| Max drawdown BBCA (V1) | No filter | | R-D2 | | |
| Max drawdown BBNI (V1) | No filter | | R-D2 | | |
| Max drawdown BBRI (V1) | No filter | | R-D2 | | |
| Max drawdown BMRI (V1) | No filter | | R-D2 | | |
| Volatility (ann.) BBCA (V1/V5) | No filter | | R-D3 | | |
| Volatility (ann.) BBNI (V1/V5) | No filter | | R-D3 | | |
| Volatility (ann.) BBRI (V1/V5) | No filter | | R-D3 | | |
| Volatility (ann.) BMRI (V1/V5) | No filter | | R-D3 | | |
| Yearly return BBCA 2022 (V7) | Ticker = BBCA (filtered view) | | R-D4 | | |
| Monthly return BMRI 2020-03 (V8) | Ticker = BMRI; month range includes 2020-03 | | R-D5 | | |

Run date, Job run ID of the Gold build, and screenshot file names: _to be filled_.
