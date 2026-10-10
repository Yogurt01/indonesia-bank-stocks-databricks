"""Pure-Python unit tests for the Spark-free helpers (D2-08, docs/TEST_STRATEGY.md §1).

Run locally from the repository root:  python tests/test_pure.py
No pytest, no Spark and no data files are needed; every input is a small hand-made example.
"""
import os
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from bank_pipeline import audit, bronze, config, dq, fixtures, rerun  # noqa: E402

HEADER = "Date,open,high,low,close,adjclose,volume,ingested_at_utc"
TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True
    return False


# ---- config ---------------------------------------------------------------------------------------------------------

@test
def config_find_repo_root():
    assert config.find_repo_root(REPO_ROOT / "notebooks") == REPO_ROOT
    assert config.find_repo_root(REPO_ROOT) == REPO_ROOT
    with tempfile.TemporaryDirectory() as empty:
        assert raises(FileNotFoundError, config.find_repo_root, empty)


@test
def config_load_and_overrides():
    cfg = config.load_config(REPO_ROOT)
    assert cfg["catalog"] == "workspace" and len(cfg["tickers"]) == 4
    same = config.load_config(REPO_ROOT, {"catalog": "", "landing_path": "  "})  # empty widgets keep the file values
    assert same["catalog"] == cfg["catalog"] and same["landing_path"] == cfg["landing_path"]
    over = config.load_config(REPO_ROOT, {"catalog": "test_cat", "landing_path": "/Volumes/test_cat/bronze/x", "tickers": []})
    assert over["catalog"] == "test_cat" and over["landing_path"] == "/Volumes/test_cat/bronze/x"
    assert len(over["tickers"]) == 4  # only catalog and landing_path are overridable


@test
def config_catalog_validation():
    # The D2-09 misconfiguration: a path typed into the catalog parameter must be rejected before any SQL runs.
    for bad in ("/Volumes/workspace/bronze/test_fixtures/failure_dup_key", "x; DROP TABLE y", "1abc", "a-b"):
        assert raises(ValueError, config.load_config, REPO_ROOT, {"catalog": bad}), bad
    assert config.load_config(REPO_ROOT, {"catalog": "_ok_1"})["catalog"] == "_ok_1"


@test
def config_table_name():
    cfg = config.load_config(REPO_ROOT)
    assert config.table_name(cfg, "silver", "daily_prices") == "workspace.silver.daily_prices"
    assert config.table_name(cfg, "ops", "run_audit") == "workspace.ops.run_audit"
    assert raises(KeyError, config.table_name, cfg, "platinum", "x")


# ---- bronze ---------------------------------------------------------------------------------------------------------

@test
def bronze_folder_and_ticker():
    cfg = config.load_config(REPO_ROOT)
    assert bronze.folder_from_path("dbfs:/Volumes/workspace/bronze/landing/bbca/BBCA.JK.csv") == "bbca"
    assert bronze.folder_from_path("/Volumes/workspace/bronze/landing/bbri/run-summary.json") == "bbri"
    assert raises(ValueError, bronze.folder_from_path, "file.csv")
    assert [bronze.ticker_for_folder(cfg, f) for f in ("bbca", "bbni", "bmri", "bbri")] == ["BBCA", "BBNI", "BMRI", "BBRI"]
    assert raises(ValueError, bronze.ticker_for_folder, cfg, "bbxx")
    assert raises(ValueError, bronze.ticker_for_folder, cfg, "BBCA")  # case matters


@test
def bronze_header_matches():
    cols = HEADER.split(",")
    assert bronze.header_matches(HEADER, cols)
    assert bronze.header_matches("﻿" + HEADER + "\r\n", cols)
    assert not bronze.header_matches("Date,open,high,low,close,volume,adjclose,ingested_at_utc", cols)  # reordered
    assert not bronze.header_matches(HEADER.replace("Date", "date"), cols)  # case differs
    assert not bronze.header_matches(None, cols)


# ---- dq and audit ---------------------------------------------------------------------------------------------------

@test
def dq_rows_and_critical_failures():
    now = datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc)
    results = [dq.CheckResult("a", "silver", "CRITICAL", True, 0, "0"),
               dq.CheckResult("b", "silver", "CRITICAL", False, 1, "0", "dup"),
               dq.CheckResult("c", "silver", "WARN", False, 4)]
    rows = dq.to_rows(results, "run-1", now)
    assert [list(r) for r in rows] == [list(dq.DQ_COLUMNS)] * 3
    assert rows[1] == {"pipeline_run_id": "run-1", "check_name": "b", "layer": "silver", "severity": "CRITICAL",
                       "passed": False, "failing_count": 1, "expected": "0", "details": "dup", "checked_at": now}
    assert [r.check_name for r in dq.critical_failures(results)] == ["b"]  # a failed WARN never blocks
    assert raises(ValueError, dq.CheckResult, "d", "gold", "ERROR", True, 0)


@test
def audit_row_builder():
    t0 = datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc)
    ok = audit.audit_row("run-1", "gold_build", "123", t0, t0 + timedelta(seconds=85), "SUCCEEDED", 7548, 7544, 0)
    assert list(ok) == list(audit.AUDIT_COLUMNS) and ok["job_run_id"] == "123" and ok["error_message"] is None
    failed = audit.audit_row("run-1", "silver_transform", "", t0, t0, "FAILED", 7548, None, None, "E" * 5000)
    assert failed["job_run_id"] is None  # interactive run
    assert len(failed["error_message"]) == audit.MAX_ERROR_LENGTH and failed["error_message"].endswith("...")
    assert raises(ValueError, audit.audit_row, "r", "t", "", t0, t0, "OK")


# ---- fixtures -------------------------------------------------------------------------------------------------------

@test
def fixtures_replace_row_with_previous():
    rows = [f"2019-01-0{i},{i}.0,{i}.0,{i}.0,{i}.0,{i}.0,{i}0,2026-10-09 05:43:40+00:00" for i in range(1, 6)]
    for nl, trailing in (("\n", True), ("\r\n", True), ("\n", False), ("\r\n", False)):
        text = nl.join([HEADER, *rows]) + (nl if trailing else "")
        new, replaced, duplicated = fixtures.replace_row_with_previous(text, 3)
        out = new.split(nl)[:-1] if trailing else new.split(nl)
        assert out[0] == HEADER and len(out) == len(rows) + 1
        assert out[3] == out[2] == rows[1] and replaced == rows[2] and duplicated == rows[1]
        assert out[1:3] + out[4:] == rows[:2] + rows[3:]
        assert new.endswith(nl) == trailing and (("\r\n" in new) == (nl == "\r\n"))
        assert fixtures.first_field(replaced) == "2019-01-03" and fixtures.first_field(duplicated) == "2019-01-02"
    for bad in (0, 1, 6):
        assert raises(ValueError, fixtures.replace_row_with_previous, HEADER + "\n" + "\n".join(rows) + "\n", bad)


@test
def fixtures_root_derived_from_catalog():
    cfg = config.load_config(REPO_ROOT, {"catalog": "test_cat"})
    assert fixtures.fixture_root(cfg) == "/Volumes/test_cat/bronze/test_fixtures/failure_dup_key"


# ---- rerun ----------------------------------------------------------------------------------------------------------

@test
def rerun_pick_versions():
    write = "CREATE OR REPLACE TABLE AS SELECT"
    assert rerun.pick_versions([(0, write), (1, write), (2, write), (3, write)]) == (2, 3)  # D2-07 case
    assert rerun.pick_versions([(0, write), (1, write), (2, "OPTIMIZE"), (3, "VACUUM END")]) == (0, 1)
    assert rerun.pick_versions([(7, "WRITE"), (5, "WRITE"), (6, "optimize")]) == (5, 7)
    assert rerun.pick_versions([(0, write)]) == (None, 0) and rerun.pick_versions([]) == (None, None)


@test
def rerun_evaluate():
    base = dict(keys=("ticker",), rows_prev=4, rows_latest=4, dup_keys=0, missing_rows=0,
                mismatched_non_double=0, max_double_diff=0.0, note="")
    assert rerun.evaluate(base) == "PASS"
    assert rerun.evaluate({**base, "max_double_diff": 5e-10}) == "PASS"
    assert rerun.evaluate({**base, "max_double_diff": None}) == "PASS"
    for key, value in (("max_double_diff", 2e-9), ("max_double_diff", float("inf")), ("rows_latest", 5),
                       ("dup_keys", 1), ("missing_rows", 1), ("mismatched_non_double", 1), ("note", "columns differ")):
        assert rerun.evaluate({**base, key: value}) == "FAIL", key
    assert rerun.evaluate(dict(keys=None, rows_prev=0, rows_latest=0, note="")) == "PASS"
    assert rerun.evaluate(dict(keys=None, rows_prev=0, rows_latest=1, note="")) == "FAIL"


def main():
    failures = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL  {fn.__name__}\n{traceback.format_exc()}")
    assert "pyspark" not in sys.modules, "a Spark-free module imported pyspark"
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    print("PURE TESTS PASS" if failures == 0 else "PURE TESTS FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
