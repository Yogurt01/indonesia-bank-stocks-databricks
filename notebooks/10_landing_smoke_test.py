# Databricks notebook source
# MAGIC %md
# MAGIC # 10 Landing smoke test (D1-11, completes the D1-04 Databricks read)
# MAGIC Read-only: checks the 8 landed files (DEC-05) and reads the real daily CSVs. Writes no table.
# MAGIC Expected for the 2026-10-08 snapshot (from docs/DATASET.md; not hard-coded below): 1,887 data rows per ticker,
# MAGIC dates 2019-01-01 to 2026-10-08, one run_id shared by all four tickers. Not yet run in Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog (empty = config)")
dbutils.widgets.text("landing_path", "", "Landing path (empty = config)")

# COMMAND ----------

import os
import sys

# Same bootstrap as 00_setup: put <repo>/src on sys.path first (DEC-10 import assumption; fallback is %run).
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from bank_pipeline.config import find_repo_root, load_config

repo_root = find_repo_root(os.getcwd())
cfg = load_config(repo_root, {
    "catalog": dbutils.widgets.get("catalog"),
    "landing_path": dbutils.widgets.get("landing_path"),
})
landing_path = cfg["landing_path"].rstrip("/")
print(f"repo_root={repo_root}  landing_path={landing_path}")

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import types as T


def list_names(folder):
    try:
        return {f.name for f in dbutils.fs.ls(folder)}
    except Exception as exc:  # a missing folder raises; report it as "files absent" rather than abort the whole check
        print(f"Cannot list {folder}: {exc}")
        return set()


results = []
for t in cfg["tickers"]:
    folder = f"{landing_path}/{t['folder']}"
    csv_name = f"{t['source_symbol']}.csv"
    csv_path, json_path = f"{folder}/{csv_name}", f"{folder}/run-summary.json"
    names = list_names(folder)
    csv_exists, json_exists = csv_name in names, "run-summary.json" in names

    header_ok = csv_rows = date_min = date_max = None
    if csv_exists:
        # Compare the raw header text, not Spark's parsed names, so renamed or reordered columns are caught.
        header = dbutils.fs.head(csv_path, 4096).splitlines()[0].lstrip("﻿")
        header_ok = header.split(",") == cfg["source_columns"]
        csv_rows = spark.read.text(csv_path).count() - 1  # minus the header line
        # No inferSchema, so every column stays STRING, as in Bronze.
        prices = spark.read.option("header", True).csv(csv_path)
        bounds = prices.agg(F.min("Date").alias("lo"), F.max("Date").alias("hi")).first()
        date_min, date_max = bounds["lo"], bounds["hi"]

    json_ticker = json_daily_rows = source_run_id = None
    if json_exists:
        summary = spark.read.option("multiLine", True).json(json_path)
        print(f"run-summary.json schema for {t['ticker']} (owner: confirm the field names):")
        summary.printSchema()
        doc = summary.first().asDict(recursive=True)
        # Field names are read defensively: a missing key yields None and the row fails below.
        json_ticker = doc.get("ticker")
        source_run_id = doc.get("run_id")
        daily = (doc.get("intervals") or {}).get("1d") or {}
        json_daily_rows = daily.get("rows")
        print(f"  {t['ticker']}: json ticker={json_ticker} daily rows={json_daily_rows} "
              f"date_max={daily.get('date_max')} run_id={source_run_id}")

    rows_match = csv_rows is not None and json_daily_rows is not None and csv_rows == json_daily_rows
    results.append((t["ticker"], csv_exists, json_exists, header_ok, csv_rows, json_daily_rows, rows_match,
                    json_ticker, date_min, date_max, source_run_id))

# COMMAND ----------

schema = T.StructType([
    T.StructField("ticker", T.StringType()),
    T.StructField("csv_exists", T.BooleanType()),
    T.StructField("json_exists", T.BooleanType()),
    T.StructField("header_ok", T.BooleanType()),
    T.StructField("csv_rows", T.LongType()),
    T.StructField("json_daily_rows", T.LongType()),
    T.StructField("rows_match", T.BooleanType()),
    T.StructField("json_ticker", T.StringType()),
    T.StructField("date_min", T.StringType()),
    T.StructField("date_max", T.StringType()),
    T.StructField("source_run_id", T.StringType()),
])
result_df = spark.createDataFrame(results, schema)
display(result_df)

# The JSON "ticker" field holds the source symbol (for example BBCA.JK), so compare it with source_symbol.
symbols = {t["ticker"]: t["source_symbol"] for t in cfg["tickers"]}
row_ok = [
    bool(r[1] and r[2] and r[3] and r[6] and r[7] == symbols[r[0]])
    for r in results
]
run_ids = {r[10] for r in results}
print("Distinct source run_ids:", run_ids, "(expected one shared run_id)")
overall = len(results) == len(cfg["tickers"]) and all(row_ok)
print("SMOKE TEST", "PASS" if overall else "FAIL")
