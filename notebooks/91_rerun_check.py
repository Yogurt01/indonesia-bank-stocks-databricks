# Databricks notebook source
# MAGIC %md
# MAGIC # 91 Rerun check (D2-07)
# MAGIC Read-only. After running the Job twice on the same input, compares the latest Delta version of every Bronze, Silver and Gold
# MAGIC table with the previous one (time travel), ignoring run-specific columns. Writes no table. Method: `docs/TEST_STRATEGY.md` §3.
# MAGIC Not yet run in Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog (empty = config)")

# COMMAND ----------

import os
import sys

# Same bootstrap as 00_setup (import via sys.path verified in D1-10).
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from bank_pipeline.config import find_repo_root, load_config, table_name

repo_root = find_repo_root(os.getcwd())
cfg = load_config(repo_root, {"catalog": dbutils.widgets.get("catalog")})
print(f"repo_root={repo_root}  catalog={cfg['catalog']}")

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql import types as T

from bank_pipeline import rerun

results = []
for (layer, name), keys in rerun.TABLE_KEYS.items():
    table = table_name(cfg, layer, name)
    history = rerun.table_history(spark, table)
    prev_v, latest_v = rerun.pick_versions(history)
    ops = dict(history)
    if prev_v is None:
        print(f"{table}: no previous data-writing version -> SKIPPED (history={history})")
        results.append((table, prev_v, latest_v, None, None, None, None, None, None, "SKIPPED", "no previous version"))
        continue
    print(f"{table}: comparing version {prev_v} ({ops[prev_v]}) with {latest_v} ({ops[latest_v]})")
    m = rerun.compare_versions(rerun.read_version(spark, table, prev_v), rerun.read_version(spark, table, latest_v), keys)
    results.append((table, prev_v, latest_v, m["rows_prev"], m["rows_latest"], m["dup_keys"], m["missing_rows"],
                    m["mismatched_non_double"], m["max_double_diff"], rerun.evaluate(m), m["note"] or None))

# COMMAND ----------

schema = T.StructType([
    T.StructField("table", T.StringType()),
    T.StructField("version_prev", T.LongType()),
    T.StructField("version_latest", T.LongType()),
    T.StructField("rows_prev", T.LongType()),
    T.StructField("rows_latest", T.LongType()),
    T.StructField("dup_keys", T.LongType()),
    T.StructField("missing_rows", T.LongType()),
    T.StructField("mismatched_non_double", T.LongType()),
    T.StructField("max_double_diff", T.DoubleType()),
    T.StructField("result", T.StringType()),
    T.StructField("note", T.StringType()),
])
display(spark.createDataFrame(results, schema))

# Links this comparison to the two Job runs that produced the compared versions.
display(spark.table(table_name(cfg, "ops", "run_audit"))
        .filter(F.col("task_name") == "gold_build")
        .orderBy(F.col("started_at").desc())
        .select("pipeline_run_id", "job_run_id", "status", "started_at", "ended_at")
        .limit(2))

overall = all(r[9] == "PASS" for r in results)
print("RERUN CHECK", "PASS" if overall else "FAIL",
      f"({sum(r[9] == 'PASS' for r in results)} PASS, {sum(r[9] == 'FAIL' for r in results)} FAIL, "
      f"{sum(r[9] == 'SKIPPED' for r in results)} SKIPPED of {len(results)} tables)")
