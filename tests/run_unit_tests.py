# Databricks notebook source
# MAGIC %md
# MAGIC # Unit tests (D2-08, Spark part)
# MAGIC Calls the real functions in `src/bank_pipeline/silver.py` and `gold.py` on tiny hand-made DataFrames, with small windows (N = M = 3)
# MAGIC and hand-computed expected values. Read-only: no table writes. The Spark-free helpers are covered by `tests/test_pure.py`.
# MAGIC Method: `docs/TEST_STRATEGY.md` §1. Not yet run in Databricks.

# COMMAND ----------

import os
import sys

# Same bootstrap as the pipeline notebooks: this notebook lives in <repo>/tests, a sibling of <repo>/src.
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import math
import statistics
from datetime import date

from bank_pipeline import gold, silver

TOL = 1e-12
N = M = 3
A = 252
D = date.fromisoformat
results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail if not condition else ''}")


def close(a, b):
    return a is not None and b is not None and abs(a - b) <= TOL


def run(name, fn):
    try:
        fn()
    except Exception as exc:  # a crashing test is a failed test, and the remaining tests still run
        check(name, False, f"{type(exc).__name__}: {exc}")

# COMMAND ----------

# Two tickers x four days. Day 1: both zero (holiday-like); day 2: both trade; day 3: only B trades; day 4: only A trades.
VOL_ROWS = [("A", D("2020-01-01"), 0), ("A", D("2020-01-02"), 10), ("A", D("2020-01-03"), 0), ("A", D("2020-01-06"), 5),
            ("B", D("2020-01-01"), 0), ("B", D("2020-01-02"), 20), ("B", D("2020-01-03"), 7), ("B", D("2020-01-06"), 0)]


def test_volume_status_and_base_date():
    df = silver.add_volume_status(spark.createDataFrame(VOL_ROWS, "ticker STRING, trade_date DATE, volume BIGINT"))
    got = {(r["ticker"], r["trade_date"].isoformat()): r["volume_status"] for r in df.collect()}
    expected = {("A", "2020-01-01"): "zero_all_tickers", ("B", "2020-01-01"): "zero_all_tickers",
                ("A", "2020-01-02"): "normal", ("B", "2020-01-02"): "normal",
                ("A", "2020-01-03"): "zero_partial", ("B", "2020-01-03"): "normal",
                ("A", "2020-01-06"): "normal", ("B", "2020-01-06"): "zero_partial"}
    check("volume_status: normal / zero_all_tickers / zero_partial", got == expected, f"got={got}")
    check("base_date = first date on which every ticker is normal", silver.base_date(df, 2) == D("2020-01-02"),
          f"got={silver.base_date(df, 2)}")


run("volume_status_and_base_date", test_volume_status_and_base_date)

# COMMAND ----------

TS = "2026-10-09 05:43:40.875883+00:00"
BRONZE_COLS = "case STRING, source_date STRING, open STRING, high STRING, low STRING, close STRING, adjclose STRING, " \
              "volume STRING, ingested_at_utc STRING, _rescued_data STRING"
REJECT_CASES = [  # case, source_date, open, high, low, close, adjclose, volume, ingested_at_utc, _rescued_data -> expected codes
    (("valid", "2020-01-02", "10", "11", "9", "10.5", "10.0", "100", TS, None), []),
    (("invalid_date", "2020-13-45", "10", "11", "9", "10.5", "10.0", "100", TS, None), ["invalid_date"]),
    (("invalid_price", "2020-01-02", "abc", "11", "9", "10.5", "10.0", "100", TS, None), ["invalid_price"]),
    (("non_positive_price", "2020-01-02", "10", "11", "9", "10.5", "0", "100", TS, None), ["non_positive_price"]),
    (("ohlc_inconsistent", "2020-01-02", "10", "11", "12", "10.5", "10.0", "100", TS, None), ["ohlc_inconsistent"]),
    (("invalid_volume", "2020-01-02", "10", "11", "9", "10.5", "10.0", "-5", TS, None), ["invalid_volume"]),
    (("rescued_data_present", "2020-01-02", "10", "11", "9", "10.5", "10.0", "100", TS, '{"x":"1"}'), ["rescued_data_present"]),
]


def test_reject_reasons():
    df = spark.createDataFrame([row for row, _ in REJECT_CASES], BRONZE_COLS)
    got = {r["case"]: list(r["reject_reasons"]) for r in silver.reject_reasons(silver.parse_bronze(df)).collect()}
    for (row, expected) in REJECT_CASES:
        check(f"reject_reasons: {row[0]} -> {expected}", got.get(row[0]) == expected, f"got={got.get(row[0])}")
    parsed = silver.parse_bronze(df).filter("case = 'valid'").select("p.source_ingested_at").first()[0]
    check("parse_bronze: ingested_at_utc with +00:00 parses to TIMESTAMP", parsed is not None, f"got={parsed}")


def test_duplicate_keys():
    df = spark.createDataFrame([("A", D("2020-01-02")), ("A", D("2020-01-02")), ("A", D("2020-01-03"))], "ticker STRING, trade_date DATE")
    got = [(r["ticker"], r["trade_date"].isoformat(), r["count"]) for r in silver.duplicate_keys(df).collect()]
    check("duplicate_keys: one key occurring twice", got == [("A", "2020-01-02", 2)], f"got={got}")


run("reject_reasons", test_reject_reasons)
run("duplicate_keys", test_duplicate_keys)

# COMMAND ----------

# One ticker, six rows; 2020-01-03 is a flagged flat row carrying the previous price (as verified in Silver).
SILVER_COLS = "ticker STRING, trade_date DATE, close DOUBLE, adjclose DOUBLE, volume BIGINT, volume_status STRING"
DAILY_ROWS = [("A", D("2020-01-01"), 100.0, 100.0, 10, "normal"),
              ("A", D("2020-01-02"), 110.0, 110.0, 20, "normal"),
              ("A", D("2020-01-03"), 110.0, 110.0, 0, "zero_partial"),
              ("A", D("2020-01-06"), 99.0, 99.0, 30, "normal"),
              ("A", D("2020-01-07"), 120.0, 120.0, 40, "normal"),
              ("A", D("2020-01-08"), 108.0, 108.0, 50, "normal")]
BASE = D("2020-01-01")
# Hand-computed simple returns on normal rows; 2020-01-06 is measured from the previous NORMAL row (110), across the flagged gap.
R2, R4, R5, R6 = 110 / 100 - 1, 99 / 110 - 1, 120 / 99 - 1, 108 / 120 - 1


def build_daily_rows():
    df = gold.build_daily(spark.createDataFrame(DAILY_ROWS, SILVER_COLS), BASE, N, M, A)
    return df, {r["trade_date"].isoformat(): r for r in df.collect()}


def test_daily_return_and_vol():
    _, g = build_daily_rows()
    check("daily_return NULL on the base row", g["2020-01-01"]["daily_return"] is None)
    check("daily_return NULL on the flagged row", g["2020-01-03"]["daily_return"] is None)
    check("daily_return from the previous normal row", close(g["2020-01-02"]["daily_return"], R2))
    check("daily_return across a flagged gap uses the previous normal row", close(g["2020-01-06"]["daily_return"], R4),
          f"got={g['2020-01-06']['daily_return']} expected={R4}")
    leading = [d for d in ("2020-01-01", "2020-01-02", "2020-01-06") if g[d]["vol_60d_ann"] is None]
    check(f"vol (N={N}): {N} leading NULL normal rows", len(leading) == N, f"null on {leading}")
    check("vol NULL on the flagged row", g["2020-01-03"]["vol_60d_ann"] is None)
    exp7 = statistics.stdev([R2, R4, R5]) * math.sqrt(A)
    exp8 = statistics.stdev([R4, R5, R6]) * math.sqrt(A)
    check("vol = stddev_samp(last N returns) * sqrt(A) on 2020-01-07", close(g["2020-01-07"]["vol_60d_ann"], exp7),
          f"got={g['2020-01-07']['vol_60d_ann']} expected={exp7}")
    check("vol window slides on 2020-01-08", close(g["2020-01-08"]["vol_60d_ann"], exp8))
    check("normalized_index = 100 at the base and 108 at the end",
          close(g["2020-01-01"]["normalized_index"], 100.0) and close(g["2020-01-08"]["normalized_index"], 108.0))


def test_drawdown_and_summary():
    df, g = build_daily_rows()
    check("drawdown 0 on a new peak (2020-01-02, 2020-01-07)", g["2020-01-02"]["drawdown"] == 0 and g["2020-01-07"]["drawdown"] == 0)
    check("drawdown after a drop = 99/110 - 1", close(g["2020-01-06"]["drawdown"], 99 / 110 - 1))
    check("running_peak 120 after the new high", close(g["2020-01-08"]["running_peak"], 120.0))
    s = gold.build_summary(df, BASE, A).first()
    check("total_return = 108/100 - 1", close(s["total_return"], 108 / 100 - 1))
    check("vol_full_ann = stddev_samp(all returns) * sqrt(A)", close(s["vol_full_ann"], statistics.stdev([R2, R4, R5, R6]) * math.sqrt(A)))
    # 99/110 and 108/120 are both exactly the double nearest 0.9, so the two drops tie; the earliest is the trough.
    assert 99 / 110 == 108 / 120
    check("max_drawdown and trough_date (earliest of a tie)", close(s["max_drawdown"], 99 / 110 - 1) and s["trough_date"] == D("2020-01-06"),
          f"got={s['max_drawdown']} {s['trough_date']}")
    # DEC-14: the earliest date <= trough whose adjclose equals the running peak at the trough (110), i.e. the trading day the peak
    # was set (2020-01-02), not the flat holiday row 2020-01-03 that carries the same price (the old rule returned 2020-01-03).
    check("peak_date = day the peak was set, not the flat row after it (2020-01-02)", s["peak_date"] == D("2020-01-02"),
          f"got={s['peak_date']}")
    check("current_drawdown = 108/120 - 1, last_trade_date = 2020-01-08",
          close(s["current_drawdown"], 108 / 120 - 1) and s["last_trade_date"] == D("2020-01-08"))


def test_rel_volume():
    _, g = build_daily_rows()
    check(f"rel_volume (M={M}): NULL until {M} previous normal rows",
          all(g[d]["rel_volume_60d"] is None for d in ("2020-01-01", "2020-01-02", "2020-01-06", "2020-01-03")))
    # Excluding day t: 40 / avg(10, 20, 30) = 2.0 (including t would give 40 / 30).
    check("rel_volume excludes day t (2020-01-07 = 2.0)", close(g["2020-01-07"]["rel_volume_60d"], 2.0),
          f"got={g['2020-01-07']['rel_volume_60d']}")
    check("rel_volume window slides (2020-01-08 = 50/30)", close(g["2020-01-08"]["rel_volume_60d"], 50 / 30))


def test_peak_retouch():
    # The price returns to exactly the peak level (110 on 2020-01-06) before the trough; DEC-14 reports the first day it was set.
    rows = [("A", D("2020-01-01"), 100.0, 100.0, 10, "normal"),
            ("A", D("2020-01-02"), 110.0, 110.0, 20, "normal"),
            ("A", D("2020-01-03"), 105.0, 105.0, 30, "normal"),
            ("A", D("2020-01-06"), 110.0, 110.0, 40, "normal"),
            ("A", D("2020-01-07"), 90.0, 90.0, 50, "normal")]
    daily = gold.build_daily(spark.createDataFrame(rows, SILVER_COLS), BASE, N, M, A)
    s = gold.build_summary(daily, BASE, A).first()
    check("peak re-touched before the trough: peak_date = first day the level was set (2020-01-02), trough 2020-01-07",
          s["peak_date"] == D("2020-01-02") and s["trough_date"] == D("2020-01-07") and close(s["max_drawdown"], 90 / 110 - 1),
          f"got peak={s['peak_date']} trough={s['trough_date']} max_dd={s['max_drawdown']}")


run("daily_return_and_vol", test_daily_return_and_vol)
run("drawdown_and_summary", test_drawdown_and_summary)
run("peak_retouch", test_peak_retouch)
run("rel_volume", test_rel_volume)

# COMMAND ----------

PERIOD_ROWS = [("A", D("2020-01-30"), 100.0, 100.0, 10, "normal"),
               ("A", D("2020-01-31"), 105.0, 105.0, 20, "normal"),
               ("A", D("2020-02-03"), 110.0, 110.0, 30, "normal"),
               ("A", D("2020-02-04"), 99.0, 99.0, 40, "normal"),
               ("A", D("2020-02-05"), 99.0, 99.0, 0, "zero_partial")]  # flat flagged row, last date of the dataset
PERIOD_BASE = D("2020-01-30")


def periods(rows):
    daily = gold.build_daily(spark.createDataFrame(rows, SILVER_COLS), PERIOD_BASE, N, M, A)
    monthly = {r["month_start"].isoformat(): r for r in gold.build_monthly(daily, PERIOD_BASE).collect()}
    yearly = {r["year"]: r for r in gold.build_yearly(daily, PERIOD_BASE).collect()}
    return monthly, yearly


def test_monthly_yearly_running_february():
    m, y = periods(PERIOD_ROWS)
    check("monthly: first period starts at the base price (Jan = 105/100 - 1)", close(m["2020-01-01"]["monthly_return"], 105 / 100 - 1))
    check("monthly: Feb = 99/105 - 1 (month-end to month-end)", close(m["2020-02-01"]["monthly_return"], 99 / 105 - 1))
    check("is_partial: first month TRUE", m["2020-01-01"]["is_partial"] is True)
    check("is_partial: running Feb TRUE (last date 2020-02-05 < last weekday 2020-02-28)", m["2020-02-01"]["is_partial"] is True)
    check("Feb sessions: n_sessions 3, n_normal_sessions 2, avg_daily_volume over normal rows = 35",
          m["2020-02-01"]["n_sessions"] == 3 and m["2020-02-01"]["n_normal_sessions"] == 2 and close(m["2020-02-01"]["avg_daily_volume"], 35.0))
    check("yearly: 2020 = 99/100 - 1, partial", close(y[2020]["yearly_return"], 99 / 100 - 1) and y[2020]["is_partial"] is True)
    compounded = (1 + m["2020-01-01"]["monthly_return"]) * (1 + m["2020-02-01"]["monthly_return"]) - 1
    check("monthly returns compound to the yearly return", close(compounded, y[2020]["yearly_return"]))


def test_monthly_complete_february():
    rows = PERIOD_ROWS[:4] + [("A", D("2020-02-28"), 100.0, 100.0, 50, "normal")]  # last date = Feb's last weekday (Friday)
    m, y = periods(rows)
    check("is_partial: complete Feb FALSE (last date = last weekday)", m["2020-02-01"]["is_partial"] is False)
    check("monthly: Feb = 100/105 - 1", close(m["2020-02-01"]["monthly_return"], 100 / 105 - 1))
    check("yearly: 2020 still partial (2020-02-28 < 2020-12-31)", y[2020]["is_partial"] is True)


run("monthly_yearly_running_february", test_monthly_yearly_running_february)
run("monthly_complete_february", test_monthly_complete_february)

# COMMAND ----------

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
for name, _, detail in failed:
    print("FAILED:", name, detail)
assert not failed, f"{len(failed)} unit test check(s) failed"
print("UNIT TESTS PASS")
