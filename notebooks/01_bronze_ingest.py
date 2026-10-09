# Databricks notebook source
# MAGIC %md
# MAGIC # 01 Bronze ingest (D2-01, with D2-02 run audit)
# MAGIC Loads the 4 daily CSVs and 4 `run-summary.json` files from the landing Volume into `bronze.daily_prices_raw` and
# MAGIC `bronze.source_run_summary` (full overwrite, DEC-06). The Bronze DQ checks run first; a failed CRITICAL check stops the task
# MAGIC before any Bronze table is written. Design: `docs/DATA_MODEL.md` §0–§1, `docs/TEST_STRATEGY.md` §2. Not yet run in Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog (empty = config)")
dbutils.widgets.text("landing_path", "", "Landing path (empty = config)")
# The Job passes {{job.run_id}} for both; an interactive run leaves them empty.
dbutils.widgets.text("pipeline_run_id", "", "Pipeline run ID (empty = new UUID)")
dbutils.widgets.text("job_run_id", "", "Job run ID (empty when interactive)")

# COMMAND ----------

import os
import sys

# Same bootstrap as 00_setup (import via sys.path verified in D1-10).
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from bank_pipeline.config import find_repo_root, load_config, table_name

repo_root = find_repo_root(os.getcwd())
cfg = load_config(repo_root, {
    "catalog": dbutils.widgets.get("catalog"),
    "landing_path": dbutils.widgets.get("landing_path"),
})
landing_path = cfg["landing_path"].rstrip("/")
print(f"repo_root={repo_root}  catalog={cfg['catalog']}  landing_path={landing_path}")

# COMMAND ----------

import uuid
from datetime import datetime, timezone

from pyspark.sql import functions as F
from pyspark.sql import types as T

from bank_pipeline import audit, dq
from bank_pipeline.bronze import (DAILY_PRICES_RAW_COLUMNS, SOURCE_RUN_SUMMARY_COLUMNS,
                                  header_matches, ticker_for_folder)

TASK_NAME = "bronze_ingest"
LAYER = "bronze"
pipeline_run_id = dbutils.widgets.get("pipeline_run_id").strip() or str(uuid.uuid4())
job_run_id = dbutils.widgets.get("job_run_id").strip()

daily_table = table_name(cfg, "bronze", "daily_prices_raw")
summary_table = table_name(cfg, "bronze", "source_run_summary")
dq_table = table_name(cfg, "ops", "dq_results")
audit_table = table_name(cfg, "ops", "run_audit")

expected_tickers = {t["ticker"] for t in cfg["tickers"]}
symbol_by_ticker = {t["ticker"]: t["source_symbol"] for t in cfg["tickers"]}
started_at = datetime.now(timezone.utc)
print(f"pipeline_run_id={pipeline_run_id}  job_run_id={job_run_id or '(interactive)'}")

# COMMAND ----------

def with_ticker(df):
    """Add folder and ticker from the file path, through a small mapping DataFrame (no Python UDF)."""
    df = df.withColumn("folder", F.element_at(F.split("source_file", "/"), -2))
    # The glob also matches unexpected folders; validating the few distinct names raises instead of dropping rows in the join.
    for row in df.select("folder").distinct().collect():
        ticker_for_folder(cfg, row["folder"])
    mapping = spark.createDataFrame([(t["folder"], t["ticker"]) for t in cfg["tickers"]], "folder STRING, ticker STRING")
    return df.join(F.broadcast(mapping), "folder", "left")


def read_daily():
    # Every column STRING so no source value is lost; typing happens in Silver.
    schema = T.StructType([T.StructField(c, T.StringType()) for c in cfg["source_columns"]])
    df = (spark.read.format("csv")
          .option("header", True)
          .schema(schema)
          # Databricks option: values that do not fit the schema land here instead of being dropped.
          .option("rescuedDataColumn", "_rescued_data")
          .load(f"{landing_path}/*/*.JK.csv")
          # Hidden file-metadata column; availability on serverless is to be verified by this run.
          .select("*", F.col("_metadata.file_path").alias("source_file")))
    return (with_ticker(df)
            .withColumnRenamed("Date", "source_date")
            .withColumn("bronze_loaded_at", F.current_timestamp())
            .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
            .select(*DAILY_PRICES_RAW_COLUMNS))


def read_summary():
    raw = (spark.read.option("multiLine", True)
           .json(f"{landing_path}/*/run-summary.json")
           .select("*", F.col("_metadata.file_path").alias("source_file")))
    source_fields = [c for c in raw.columns if c != "source_file"]
    daily = F.col("intervals").getField("1d")  # schema confirmed in docs/evidence/d1-11-landing-smoke-test.md
    df = raw.select(
        F.col("ticker").alias("source_symbol"),
        "stock",
        F.col("run_id").alias("source_run_id"),
        daily.getField("rows").alias("daily_rows"),
        daily.getField("date_max").alias("daily_date_max"),
        daily.getField("duplicate_dates").alias("daily_duplicate_dates"),
        F.to_json(F.struct(*source_fields)).alias("raw_json"),
        "source_file",
    )
    return (with_ticker(df)
            .withColumn("bronze_loaded_at", F.current_timestamp())
            .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
            .select(*SOURCE_RUN_SUMMARY_COLUMNS))


def read_headers():
    """First line of each expected CSV; None when the file cannot be read."""
    headers = {}
    for t in cfg["tickers"]:
        path = f"{landing_path}/{t['folder']}/{t['source_symbol']}.csv"
        try:
            headers[t["ticker"]] = dbutils.fs.head(path, 4096).splitlines()[0]
        except Exception as exc:  # reported through the header check rather than aborting before the checks run
            print(f"Cannot read header of {path}: {exc}")
            headers[t["ticker"]] = None
    return headers

# COMMAND ----------

def bronze_checks(daily_df, summary_rows, csv_counts, headers):
    summary = {r["ticker"]: r for r in summary_rows}
    results = []

    missing = sorted((expected_tickers - set(csv_counts)) | (expected_tickers - set(summary)))
    results.append(dq.CheckResult("bronze_all_tickers_present", LAYER, "CRITICAL", not missing, len(missing),
                                  expected=str(len(expected_tickers)), details=f"missing={missing}"))

    bad_headers = sorted(t for t, h in headers.items() if not header_matches(h, cfg["source_columns"]))
    results.append(dq.CheckResult("bronze_header_matches", LAYER, "CRITICAL", not bad_headers, len(bad_headers),
                                  expected="0 mismatches", details=f"mismatched={bad_headers}"))

    row_diff = {t: (csv_counts.get(t), summary.get(t, {}).get("daily_rows")) for t in sorted(expected_tickers)
                if csv_counts.get(t) is None or csv_counts.get(t) != summary.get(t, {}).get("daily_rows")}
    results.append(dq.CheckResult("bronze_rows_match_run_summary", LAYER, "CRITICAL", not row_diff, len(row_diff),
                                  expected="csv rows == run-summary daily rows",
                                  details=f"(csv, json) per differing ticker={row_diff}; csv rows={csv_counts}"))

    bad_symbols = {t: summary.get(t, {}).get("source_symbol") for t in sorted(expected_tickers)
                   if summary.get(t, {}).get("source_symbol") != symbol_by_ticker[t]}
    results.append(dq.CheckResult("bronze_source_symbol_matches", LAYER, "CRITICAL", not bad_symbols, len(bad_symbols),
                                  expected="JSON ticker == config source_symbol", details=f"mismatched={bad_symbols}"))

    run_ids = sorted({r["source_run_id"] for r in summary_rows})
    results.append(dq.CheckResult("bronze_single_source_run_id", LAYER, "WARN", len(run_ids) == 1,
                                  max(len(run_ids) - 1, 0), expected="1", details=f"run_ids={run_ids}"))

    rescued = daily_df.filter(F.col("_rescued_data").isNotNull()).count()
    results.append(dq.CheckResult("bronze_rescued_data_empty", LAYER, "WARN", rescued == 0, rescued,
                                  expected="0", details=f"rows with _rescued_data={rescued}"))
    return results

# COMMAND ----------

stats = {"rows_in": None, "rows_out": None, "rows_rejected": None}


def run_bronze():
    daily_df = read_daily()
    summary_df = read_summary()
    headers = read_headers()

    # Small results only: at most one row per ticker.
    csv_counts = {r["ticker"]: r["count"] for r in daily_df.groupBy("ticker").count().collect()}
    summary_rows = [r.asDict() for r in summary_df.select("ticker", "source_symbol", "source_run_id", "daily_rows").collect()]
    stats["rows_in"] = sum(csv_counts.values())

    results = bronze_checks(daily_df, summary_rows, csv_counts, headers)
    dq.write_results(spark, dq_table, results, pipeline_run_id, datetime.now(timezone.utc))

    failed = dq.critical_failures(results)
    if failed:
        raise RuntimeError("Bronze CRITICAL checks failed; Bronze tables not written: "
                           + "; ".join(f"{r.check_name} ({r.details})" for r in failed))

    for df, table in ((daily_df, daily_table), (summary_df, summary_table)):
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)

    stats["rows_out"] = spark.table(daily_table).count()
    stats["rows_rejected"] = 0  # Bronze keeps every source row; rejection happens in Silver
    return results, csv_counts


try:
    check_results, rows_per_ticker = run_bronze()
except Exception as exc:
    audit.write_audit(spark, audit_table, audit.audit_row(
        pipeline_run_id, TASK_NAME, job_run_id, started_at, datetime.now(timezone.utc), "FAILED",
        stats["rows_in"], stats["rows_out"], stats["rows_rejected"], f"{type(exc).__name__}: {exc}"))
    raise

audit.write_audit(spark, audit_table, audit.audit_row(
    pipeline_run_id, TASK_NAME, job_run_id, started_at, datetime.now(timezone.utc), "SUCCEEDED",
    stats["rows_in"], stats["rows_out"], stats["rows_rejected"]))

# COMMAND ----------

print("Rows per ticker written to", daily_table, ":", dict(sorted(rows_per_ticker.items())))
print("rows_in =", stats["rows_in"], " rows_out =", stats["rows_out"])
for r in check_results:
    print(f"  [{r.severity:8}] {r.check_name:32} {'PASS' if r.passed else 'FAIL'}  failing={r.failing_count}  {r.details}")
print("BRONZE PASS")
