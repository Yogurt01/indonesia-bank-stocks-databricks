# Test Results

> Consolidated results, one table per verification concern (method: `docs/TEST_STRATEGY.md`). "Owner-reported" means the owner ran it in Databricks
> and recorded the result in the cited evidence file; the coding agent has no Databricks access. The plain-Python tests were run by the agent.

## 1. Code correctness

| Test | Scope | Result | Evidence |
| ---- | ----- | ------ | -------- |
| `tests/test_pure.py` (plain Python, local) | config, Bronze helpers, DQ result rows, audit rows, failure fixture, rerun comparison, reset table list | **14/14 passed** (agent run 2026-10-10 evening; 12/12 recorded earlier, before the two reset tests were added) | `docs/evidence/d2-08-unit-tests.md`; run `python tests/test_pure.py` |
| `tests/run_unit_tests` (Spark, Databricks) | `silver.py` (volume status, base date, reject reasons, duplicate keys, timestamp parsing) and `gold.py` (returns, volatility, drawdown, peak/trough incl. DEC-14, relative volume, monthly/yearly returns, partial flags) with hand-computed values | **42/42 checks passed, UNIT TESTS PASS** (owner-reported) | `docs/evidence/d2-08-unit-tests.md` |
| Configuration and secrets review | No hard-coded environment values in code; no secrets, emails or hosts tracked; ignore rules effective | **Clean** | `docs/evidence/d2-10-config-review.md` |

## 2. Data quality

| Check set | Result | Evidence |
| --------- | ------ | -------- |
| Bronze checks (6) | All passed on normal data; 4 × 1,887 rows = the source's own run summary; 0 rescued rows | `docs/evidence/d2-01-bronze.md`, `d2-06-job.md` |
| Silver checks (14) | All passed except the expected WARN `silver_zero_partial_count` (4 known vendor gaps); quarantine 0 rows; 7,548 rows = 7,548 distinct keys; base date 2019-01-02 | `docs/evidence/d2-03-silver.md`, `d2-06-job.md` |
| Gold checks (10) | 10/10 passed; 7,544 daily rows = Silver rows from the base date; 60 leading NULL volatility rows per ticker; 16 partial periods | `docs/evidence/d2-05-gold.md`, `d2-06-job.md` |
| Peak dates (G9, after DEC-14) | Every `peak_date` is a normal trading day; peak `adjclose` = running peak at the trough | `docs/evidence/d2-05-gold.md` ("DEC-14 rebuild") |
| Full catalog | Rule, severity and latest result of every check | `docs/DQ_CATALOG.md` |

## 3. Pipeline execution

| Test | Result | Evidence |
| ---- | ------ | -------- |
| End-to-end Job run | Run 1066568616292788 succeeded in 3m38s–3m39s (the two evidence files differ by one second); the four tasks ran in dependency order; `{{job.run_id}}` reached every task | `docs/evidence/d2-06-job.md` |
| Rerun idempotency | Runs 1066568616292788 and 371194405323795 on the same input; Delta versions 2 vs 3 of all 9 tables: equal counts, 0 duplicate keys, 0 missing or mismatched rows, doubles within 1e-9 → **RERUN CHECK PASS (9/9)** | `docs/evidence/d2-07-rerun.md` |
| Induced failure | Run 164942117421206: Bronze succeeded with the fixture, Silver **stopped** on `silver_no_duplicate_keys`, Gold **skipped**, failure email received; Silver and Gold kept the last good run | `docs/evidence/d2-09-failure-test.md` |
| Recovery | Run 318690159636842 (new full run, default parameters): 3 SUCCEEDED audit rows; Bronze restored (0 duplicates, real files); KPIs identical to before | `docs/evidence/d2-09-failure-test.md` |
| Misconfiguration guard (unplanned) | Runs 268776281869222 and 844273765778101: a path typed into the `catalog` parameter was rejected in `setup` before any SQL ran; no table changed | `docs/evidence/d2-09-failure-test.md` |
| Rule-change rebuild | Run 766912259782044 rebuilt Gold with DEC-14; `total_return` unchanged (abs_diff 0) | `docs/evidence/d2-05-gold.md` |
| Clean-state reproduction | Reset dropped all 11 tables (schemas and landed files kept); Job run 994907076175214 with default parameters rebuilt everything: same row counts (4 × 1,887; Gold 7,544 / 376 / 32 / 4), same volume-status counts, `total_return` Silver = Gold (abs_diff 0) with identical values, identical peak/trough dates, all `sql/validation` expectations met, the dashboard unchanged after refresh | `docs/evidence/d3-04-clean-state.md` |

Observed runtimes: 3m38s–3m39s, 3m43s, 5m41s (the last after about 9.5 h idle, likely a serverless cold start, not verified); failing run 1m45s.

## 4. Business-metric correctness

| Check | Result | Evidence |
| ----- | ------ | -------- |
| G6: `total_return` recomputed from Silver vs Gold | abs_diff = 0 for all four tickers (before and after the DEC-14 rebuild) | `docs/evidence/d2-05-gold.md` |
| R-D1 total return, R-D2 max drawdown, R-D3 volatility (Silver vs Gold vs dashboard, 4 tickers each) | 12/12 match; abs_diff 0 | `docs/evidence/d3-03-dashboard-reconciliation.md` |
| R-D4 BBCA 2022 yearly return (filtered view) | Match (19.38%; abs_diff 0) | same |
| R-D5 BMRI 2020-03 monthly return | Match (−35.67%; identical digits shown) | same |
| R-D6 NULL volatility after the warm-up | Only on flagged zero-volume rows (10 holiday rows per ticker, plus 4 vendor-gap rows); 0 normal rows | same |
| Yearly returns compound to total return | Product of (1 + yearly) − 1 = total return within 3e-16 (BBCA, BBNI; checked by the agent from the recorded numbers) | `docs/evidence/d2-05-gold.md` |
| Dashboard cross-checks | Index = 100 on 2019-01-02 for all four; BBNI drawdown on 2020-03-24 = −66.16% = V1 max drawdown; V2/V5 tooltips match V1 | `docs/evidence/d3-01-dashboard.md` |
