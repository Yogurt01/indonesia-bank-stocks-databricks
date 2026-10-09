# Databricks notebook source
# MAGIC %md
# MAGIC # 02 Silver transform (D2-03, Silver part of D2-04)
# MAGIC Types and validates `bronze.daily_prices_raw` into `silver.daily_prices`, moves invalid rows to
# MAGIC `silver.daily_prices_quarantine`, and adds `volume_status` (full overwrite, DEC-06). The Silver DQ checks run first; a failed
# MAGIC CRITICAL check stops the task before any Silver table is written. Design: `docs/DATA_MODEL.md` §2,
# MAGIC `docs/KPI_DEFINITIONS.md` G3/G4, `docs/TEST_STRATEGY.md` §2. Not yet run in Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog (empty = config)")
dbutils.widgets.text("landing_path", "", "Landing path (empty = config)")
# The Job passes the same {{job.run_id}} to every task; an interactive run leaves them empty.
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
print(f"repo_root={repo_root}  catalog={cfg['catalog']}")

# COMMAND ----------

import uuid
from datetime import datetime, timezone

from pyspark.sql import functions as F

from bank_pipeline import audit, dq, silver

TASK_NAME = "silver_transform"
LAYER = "silver"
pipeline_run_id = dbutils.widgets.get("pipeline_run_id").strip() or str(uuid.uuid4())
job_run_id = dbutils.widgets.get("job_run_id").strip()

bronze_table = table_name(cfg, "bronze", "daily_prices_raw")
summary_table = table_name(cfg, "bronze", "source_run_summary")
silver_table = table_name(cfg, "silver", "daily_prices")
quarantine_table = table_name(cfg, "silver", "daily_prices_quarantine")
dq_table = table_name(cfg, "ops", "dq_results")
audit_table = table_name(cfg, "ops", "run_audit")

configured_tickers = sorted(t["ticker"] for t in cfg["tickers"])
started_at = datetime.now(timezone.utc)
print(f"pipeline_run_id={pipeline_run_id}  job_run_id={job_run_id or '(interactive)'}")

# COMMAND ----------

def build_silver(bronze_df, run_ids_df):
    """Return (silver candidate, quarantine candidate) DataFrames; nothing is written here."""
    flagged = silver.reject_reasons(silver.parse_bronze(bronze_df))
    is_valid = F.size("reject_reasons") == 0

    typed_cols = ["trade_date", *silver.PRICE_COLUMNS, "volume", "source_ingested_at"]
    valid = flagged.filter(is_valid).select("ticker", *[F.col(f"p.{c}").alias(c) for c in typed_cols], "source_file")
    candidate = (silver.add_volume_status(valid)
                 .join(F.broadcast(run_ids_df), "ticker", "left")
                 .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
                 .withColumn("processed_at", F.current_timestamp())
                 .select(*silver.SILVER_COLUMNS))

    quarantine = (flagged.filter(~is_valid)
                  .withColumnRenamed("pipeline_run_id", "bronze_pipeline_run_id")
                  .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
                  .withColumn("quarantined_at", F.current_timestamp())
                  .select(*silver.QUARANTINE_COLUMNS))
    return candidate, quarantine

# COMMAND ----------

def count_where(df, condition):
    return df.filter(condition).count()


def silver_checks(candidate, quarantine, bronze_rows, base):
    results = []
    silver_rows, quarantine_rows = candidate.count(), quarantine.count()

    dups = silver.duplicate_keys(candidate)
    n_dups = dups.count()
    sample = [f"{r['ticker']}@{r['trade_date']}x{r['count']}" for r in dups.orderBy("ticker", "trade_date").limit(10).collect()]
    results.append(dq.CheckResult("silver_no_duplicate_keys", LAYER, "CRITICAL", n_dups == 0, n_dups,
                                  expected="0", details=f"first duplicated keys={sample}"))

    diff = bronze_rows - (silver_rows + quarantine_rows)
    results.append(dq.CheckResult("silver_reconciles_with_bronze", LAYER, "CRITICAL", diff == 0, abs(diff),
                                  expected="silver + quarantine = bronze",
                                  details=f"bronze={bronze_rows} silver={silver_rows} quarantine={quarantine_rows}"))

    key_cols = ["ticker", "trade_date", *silver.PRICE_COLUMNS, "volume", "volume_status"]
    n_nulls = count_where(candidate, " OR ".join(f"`{c}` IS NULL" for c in key_cols))
    results.append(dq.CheckResult("silver_no_nulls", LAYER, "CRITICAL", n_nulls == 0, n_nulls,
                                  expected="0", details=f"columns checked={key_cols}"))

    # These three rules are already enforced by quarantine; a hit here means a logic bug, so they are CRITICAL.
    n_nonpos = count_where(candidate, " OR ".join(f"`{c}` <= 0" for c in silver.PRICE_COLUMNS))
    results.append(dq.CheckResult("silver_positive_prices", LAYER, "CRITICAL", n_nonpos == 0, n_nonpos, expected="0"))
    n_ohlc = count_where(candidate, "low > least(open, close) OR high < greatest(open, close)")
    results.append(dq.CheckResult("silver_ohlc_valid", LAYER, "CRITICAL", n_ohlc == 0, n_ohlc,
                                  expected="0", details="low <= min(open, close) and max(open, close) <= high"))
    n_negvol = count_where(candidate, "volume < 0")
    results.append(dq.CheckResult("silver_volume_non_negative", LAYER, "CRITICAL", n_negvol == 0, n_negvol, expected="0"))

    reasons = {r["reason"]: r["count"] for r in
               quarantine.select(F.explode(F.split("reject_reason", ";")).alias("reason")).groupBy("reason").count().collect()}
    results.append(dq.CheckResult("silver_quarantine_empty", LAYER, "WARN", quarantine_rows == 0, quarantine_rows,
                                  expected="0", details=f"rows per reason={reasons}"))

    union_dates = candidate.select("trade_date").distinct().count()
    per_ticker = {r["ticker"]: r["n"] for r in
                  candidate.groupBy("ticker").agg(F.countDistinct("trade_date").alias("n")).collect()}
    differing = {t: per_ticker.get(t, 0) for t in configured_tickers if per_ticker.get(t, 0) != union_dates}
    results.append(dq.CheckResult("silver_same_date_set", LAYER, "WARN", not differing, len(differing),
                                  expected=f"every ticker has all {union_dates} dates", details=f"differing={differing}"))

    n_not_flat = silver.zero_volume_not_flat(candidate).count()
    results.append(dq.CheckResult("silver_zero_volume_rows_flat", LAYER, "WARN", n_not_flat == 0, n_not_flat,
                                  expected="0", details="volume = 0 but OHLC not flat or close != previous close"))

    n_adj = silver.flat_rows_adjclose_not_carried(candidate).count()
    results.append(dq.CheckResult("silver_flat_rows_adjclose_carried", LAYER, "WARN", n_adj == 0, n_adj,
                                  expected="0", details="volume = 0 but adjclose != previous adjclose"))

    n_partial = count_where(candidate, "volume_status = 'zero_partial'")
    partial = [f"{r['ticker']}@{r['trade_date']}" for r in
               candidate.filter("volume_status = 'zero_partial'").select("ticker", "trade_date")
                        .orderBy("trade_date", "ticker").limit(50).collect()]
    results.append(dq.CheckResult("silver_zero_partial_count", LAYER, "WARN", n_partial == 0, n_partial,
                                  expected="4 for the 2026-10-08 snapshot", details=f"rows (first 50)={partial}"))

    n_zero_all = count_where(candidate, "volume_status = 'zero_all_tickers'")
    results.append(dq.CheckResult("silver_zero_all_tickers_count", LAYER, "INFO", True, n_zero_all,
                                  expected="52 (13 dates x 4) for the 2026-10-08 snapshot"))

    results.append(dq.CheckResult("silver_base_date", LAYER, "INFO", True, 0,
                                  expected="2019-01-02 (to verify)", details=f"base_date={base}"))

    n_ts_null = count_where(candidate, "source_ingested_at IS NULL")
    results.append(dq.CheckResult("silver_source_ingested_at_parsed", LAYER, "WARN", n_ts_null == 0, n_ts_null,
                                  expected="0", details="rows where ingested_at_utc did not parse as TIMESTAMP"))
    return results, silver_rows, quarantine_rows

# COMMAND ----------

stats = {"rows_in": None, "rows_out": None, "rows_rejected": None}


def run_silver():
    bronze_df = spark.table(bronze_table)
    stats["rows_in"] = bronze_df.count()
    run_ids_df = spark.table(summary_table).select("ticker", "source_run_id")

    candidate, quarantine = build_silver(bronze_df, run_ids_df)
    base = silver.base_date(candidate, len(configured_tickers))

    results, silver_rows, quarantine_rows = silver_checks(candidate, quarantine, stats["rows_in"], base)
    stats["rows_rejected"] = quarantine_rows
    dq.write_results(spark, dq_table, results, pipeline_run_id, datetime.now(timezone.utc))

    failed = dq.critical_failures(results)
    if failed:
        raise RuntimeError("Silver CRITICAL checks failed; Silver tables not written: "
                           + "; ".join(f"{r.check_name} ({r.details})" for r in failed))

    # The quarantine table is written even when empty, so it always exists for queries and reruns.
    for df, table in ((candidate, silver_table), (quarantine, quarantine_table)):
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table)

    stats["rows_out"] = spark.table(silver_table).count()
    return results, base


try:
    check_results, base = run_silver()
except Exception as exc:
    audit.write_audit(spark, audit_table, audit.audit_row(
        pipeline_run_id, TASK_NAME, job_run_id, started_at, datetime.now(timezone.utc), "FAILED",
        stats["rows_in"], stats["rows_out"], stats["rows_rejected"], f"{type(exc).__name__}: {exc}"))
    raise

audit.write_audit(spark, audit_table, audit.audit_row(
    pipeline_run_id, TASK_NAME, job_run_id, started_at, datetime.now(timezone.utc), "SUCCEEDED",
    stats["rows_in"], stats["rows_out"], stats["rows_rejected"]))

# COMMAND ----------

status_counts = {}
for r in spark.table(silver_table).groupBy("ticker", "volume_status").count().collect():
    status_counts.setdefault(r["ticker"], {})[r["volume_status"]] = r["count"]
print("rows_in =", stats["rows_in"], " rows_out =", stats["rows_out"], " rows_rejected =", stats["rows_rejected"])
for ticker in sorted(status_counts):
    print(f"  {ticker}: rows={sum(status_counts[ticker].values())}  volume_status={dict(sorted(status_counts[ticker].items()))}")
print("base_date =", base)
for r in check_results:
    print(f"  [{r.severity:8}] {r.check_name:36} {'PASS' if r.passed else 'FAIL'}  failing={r.failing_count}  {r.details}")
print("SILVER PASS")
