# Databricks notebook source
# MAGIC %md
# MAGIC # 90 Make failure fixture (D2-09, DEC-13 option A)
# MAGIC Builds a copy of the 8 landed files in the `test_fixtures` Volume, in which one data row of one ticker's CSV is replaced by
# MAGIC an exact copy of the previous row. The row count is unchanged, so Bronze passes and Silver must stop on `silver_no_duplicate_keys`.
# MAGIC The real landing Volume is only read, never modified. Idempotent: the fixture folder is deleted and rebuilt on every run.
# MAGIC Procedure: `docs/RUNBOOK.md`, `docs/TEST_STRATEGY.md` §3. Not yet run in Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog (empty = config)")
dbutils.widgets.text("ticker_folder", "bbca", "Ticker folder to corrupt")
dbutils.widgets.text("row_to_replace", "100", "Data row to replace (1-based, header excluded)")

# COMMAND ----------

import os
import sys

# Same bootstrap as 00_setup (import via sys.path verified in D1-10).
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from bank_pipeline.config import find_repo_root, load_config

repo_root = find_repo_root(os.getcwd())
cfg = load_config(repo_root, {"catalog": dbutils.widgets.get("catalog")})
print(f"repo_root={repo_root}  catalog={cfg['catalog']}")

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import types as T

from bank_pipeline import fixtures
from bank_pipeline.bronze import ticker_for_folder

ticker_folder = dbutils.widgets.get("ticker_folder").strip()
row_to_replace = int(dbutils.widgets.get("row_to_replace").strip())
target_ticker = ticker_for_folder(cfg, ticker_folder)  # raises on an unknown folder

source_root = cfg["landing_path"].rstrip("/")
root = fixtures.fixture_root(cfg)
catalog, bronze_schema = cfg["catalog"], cfg["schemas"]["bronze"]
print(f"source={source_root}\nfixture={root}\ncorrupt {ticker_folder} ({target_ticker}) data row {row_to_replace}")

# COMMAND ----------

spark.sql(f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`{bronze_schema}`.`{fixtures.FIXTURE_VOLUME}`")

# Rebuild from scratch so a rerun never stacks a second modification on top of the first.
try:
    dbutils.fs.rm(root, True)
except Exception as exc:  # nothing to delete on the first run
    print(f"(no previous fixture to remove: {exc})")

for t in cfg["tickers"]:
    dst_folder = f"{root}/{t['folder']}"
    dbutils.fs.mkdirs(dst_folder)
    for name in (f"{t['source_symbol']}.csv", "run-summary.json"):
        dbutils.fs.cp(f"{source_root}/{t['folder']}/{name}", f"{dst_folder}/{name}")

# COMMAND ----------

target = next(t for t in cfg["tickers"] if t["folder"] == ticker_folder)
csv_path = f"{root}/{ticker_folder}/{target['source_symbol']}.csv"

size = next(f.size for f in dbutils.fs.ls(f"{root}/{ticker_folder}") if f.name == f"{target['source_symbol']}.csv")
text = dbutils.fs.head(csv_path, 10_000_000)
# head() silently truncates at maxBytes; a truncated file would be rewritten with rows missing.
assert len(text.encode("utf-8")) == size, f"read {len(text.encode('utf-8'))} bytes of {size}; file was truncated"

new_text, replaced_line, duplicated_line = fixtures.replace_row_with_previous(text, row_to_replace)
dbutils.fs.put(csv_path, new_text, True)
print("replaced row :", replaced_line)
print("now a copy of:", duplicated_line)

# COMMAND ----------

# Verify the fixture the way Bronze reads it: every column STRING, ticker from the folder.
schema = T.StructType([T.StructField(c, T.StringType()) for c in cfg["source_columns"]])
mapping = spark.createDataFrame([(t["folder"], t["ticker"]) for t in cfg["tickers"]], "folder STRING, ticker STRING")
fixture_df = (spark.read.format("csv").option("header", True).schema(schema).load(f"{root}/*/*.JK.csv")
              .select("*", F.element_at(F.split(F.col("_metadata.file_path"), "/"), -2).alias("folder"))
              .join(F.broadcast(mapping), "folder", "left"))

counts = {r["ticker"]: r["count"] for r in fixture_df.groupBy("ticker").count().collect()}
summary = (spark.read.option("multiLine", True).json(f"{root}/*/run-summary.json")
           .select(F.element_at(F.split(F.col("_metadata.file_path"), "/"), -2).alias("folder"),
                   F.col("intervals").getField("1d").getField("rows").alias("daily_rows"))
           .join(F.broadcast(mapping), "folder", "left"))
expected_rows = {r["ticker"]: r["daily_rows"] for r in summary.collect()}

dups = (fixture_df.groupBy("ticker", "Date").count().filter(F.col("count") > 1)
        .select("ticker", "Date", "count").collect())
dups_by_ticker = {}
for r in dups:  # at most a handful of rows: the duplicated keys
    dups_by_ticker.setdefault(r["ticker"], []).append(r["Date"])

print("rows per ticker      :", dict(sorted(counts.items())), "(expected = run-summary daily rows:", dict(sorted(expected_rows.items())), ")")
print("duplicated keys      :", dups_by_ticker)
print("replaced original Date:", fixtures.first_field(replaced_line), "| duplicated Date:", fixtures.first_field(duplicated_line))

assert counts == expected_rows, "row counts changed; Bronze would fail bronze_rows_match_run_summary instead of reaching Silver"
assert dups_by_ticker == {target_ticker: [fixtures.first_field(duplicated_line)]}, \
    f"expected exactly 1 duplicated key in {target_ticker} and 0 elsewhere, got {dups_by_ticker}"

# COMMAND ----------

print("Use this landing_path override for the failing Job run:")
print(f"  landing_path = {root}")
print("FIXTURE READY")
