# D2-08 Unit tests

> Method and coverage: `docs/TEST_STRATEGY.md` §1. Times are UTC+07.

| Test file | Where | Run by | When | Result |
| --------- | ----- | ------ | ---- | ------ |
| `tests/run_unit_tests.py` (Spark: `silver.py`, `gold.py`, including the DEC-14 `peak_date` cases) | Databricks serverless notebook from the Git folder | Owner (owner-reported; not independently verified by the coding agent) | 2026-10-10, about 11:50–12:02 | **42/42 checks passed, `UNIT TESTS PASS`** |
| `tests/test_pure.py` (config, bronze helpers, dq, audit, fixtures, rerun) | Local, plain Python | Coding agent | 2026-10-10 | **12/12 passed, `PURE TESTS PASS`** |

## What this verifies

- At least one test per critical transformation function, with hand-computed expected values (cross-checked by an independent plain-Python model)
  and small windows (N = M = 3). Both suites pass, and the commands are documented (REQ-26).
- The DEC-14 `peak_date` rule (the day the peak was set, not a flat carry-forward row) behaves as intended on a holiday-at-peak case and on a re-touch of
  the peak.
