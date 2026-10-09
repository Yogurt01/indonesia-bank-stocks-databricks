# Databricks notebook source
# MAGIC %md
# MAGIC # 03 Gold build (D2-05, Gold part of D2-04)
# MAGIC Builds the five Gold tables from `silver.daily_prices` (full overwrite, DEC-06): `dim_ticker`, `fact_daily_metrics`,
# MAGIC `fact_monthly_metrics`, `fact_yearly_metrics`, `ticker_summary`. The Gold DQ checks run on the DataFrames first; a failed
# MAGIC CRITICAL check stops the task before any Gold table is written. Design: `docs/KPI_DEFINITIONS.md`, `docs/DATA_MODEL.md` §4,
# MAGIC `docs/TEST_STRATEGY.md` §2. Not yet run in Databricks.

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

from bank_pipeline import audit, dq, gold, silver

TASK_NAME = "gold_build"
LAYER = "gold"
pipeline_run_id = dbutils.widgets.get("pipeline_run_id").strip() or str(uuid.uuid4())
job_run_id = dbutils.widgets.get("job_run_id").strip()

kpi = cfg["kpi"]
N, M, A = kpi["vol_window"], kpi["rel_volume_window"], kpi["annualization_factor"]
TOL_INDEX = 1e-9      # normalized_index and total_return identities
TOL_DRAWDOWN = 1e-12  # drawdown may only be "positive" by rounding noise
TOL_COMPOUND = 1e-9   # monthly returns compounded to the yearly return

silver_table = table_name(cfg, "silver", "daily_prices")
gold_tables = {name: table_name(cfg, "gold", name) for name in gold.TABLE_KEYS}
dq_table = table_name(cfg, "ops", "dq_results")
audit_table = table_name(cfg, "ops", "run_audit")

configured_tickers = sorted(t["ticker"] for t in cfg["tickers"])
started_at = datetime.now(timezone.utc)
print(f"pipeline_run_id={pipeline_run_id}  job_run_id={job_run_id or '(interactive)'}  N={N} M={M} A={A}")

# COMMAND ----------

def build_gold(silver_df, base, source_run_id, source_ingested_at):
    """Return {table name: DataFrame} with lineage columns; nothing is written here."""
    daily = gold.build_daily(silver_df, base, N, M, A)
    parts = {
        "dim_ticker": (gold.build_dim_ticker(cfg, spark), gold.DIM_TICKER_COLUMNS),
        "fact_daily_metrics": (daily, gold.DAILY_COLUMNS),
        "fact_monthly_metrics": (gold.build_monthly(daily, base), gold.MONTHLY_COLUMNS),
        "fact_yearly_metrics": (gold.build_yearly(daily, base), gold.YEARLY_COLUMNS),
        "ticker_summary": (gold.build_summary(daily, base, A), gold.SUMMARY_COLUMNS),
    }
    return {name: gold.with_lineage(df, source_run_id, source_ingested_at, pipeline_run_id, cols)
            for name, (df, cols) in parts.items()}

# COMMAND ----------

def count_where(df, condition):
    return df.filter(condition).count()


def gold_checks(tables, silver_df, base, n_source_run_ids):
    daily, monthly, yearly, summary = (tables[n] for n in
                                       ("fact_daily_metrics", "fact_monthly_metrics", "fact_yearly_metrics", "ticker_summary"))
    results = []

    dup_per_table = {name: tables[name].groupBy(*keys).count().filter("count > 1").count()
                     for name, keys in gold.TABLE_KEYS.items()}
    n_dups = sum(dup_per_table.values())
    results.append(dq.CheckResult("gold_unique_keys", LAYER, "CRITICAL", n_dups == 0, n_dups,
                                  expected="0 duplicated keys", details=f"per table={dup_per_table}"))

    daily_rows = daily.count()
    silver_rows = count_where(silver_df, F.col("trade_date") >= F.lit(base))
    results.append(dq.CheckResult("gold_daily_rows_match_silver", LAYER, "CRITICAL", daily_rows == silver_rows,
                                  abs(daily_rows - silver_rows), expected="fact_daily_metrics rows = Silver rows from base date",
                                  details=f"gold={daily_rows} silver={silver_rows} base_date={base}"))

    at_base = {r["ticker"]: r["normalized_index"] for r in
               daily.filter(F.col("trade_date") == F.lit(base)).select("ticker", "normalized_index").collect()}
    bad_index = {t: at_base.get(t) for t in configured_tickers
                 if at_base.get(t) is None or abs(at_base[t] - 100) > TOL_INDEX}
    results.append(dq.CheckResult("gold_index_100_at_base", LAYER, "CRITICAL", not bad_index, len(bad_index),
                                  expected="100 for every ticker", details=f"off={bad_index}"))

    n_pos_dd = count_where(daily, F.col("drawdown") > TOL_DRAWDOWN)
    results.append(dq.CheckResult("gold_drawdown_non_positive", LAYER, "CRITICAL", n_pos_dd == 0, n_pos_dd,
                                  expected="0", details=f"rows with drawdown > {TOL_DRAWDOWN}"))

    summary_tickers = sorted(r["ticker"] for r in summary.select("ticker").collect())
    # Missing or unexpected tickers, plus any ticker that appears more than once.
    n_summary_bad = len(set(summary_tickers) ^ set(configured_tickers)) + (len(summary_tickers) - len(set(summary_tickers)))
    results.append(dq.CheckResult("gold_summary_four_rows", LAYER, "CRITICAL", n_summary_bad == 0, n_summary_bad,
                                  expected=f"exactly {configured_tickers}", details=f"found={summary_tickers}"))

    last_index = daily.groupBy("ticker").agg(F.max_by("normalized_index", "trade_date").alias("last_index"))
    n_tr_bad = count_where(summary.join(last_index, "ticker", "left"),
                           F.col("last_index").isNull()
                           | (F.abs(F.col("total_return") - (F.col("last_index") / 100 - 1)) > TOL_INDEX))
    results.append(dq.CheckResult("gold_total_return_consistent", LAYER, "CRITICAL", n_tr_bad == 0, n_tr_bad,
                                  expected="total_return = last normalized_index / 100 - 1"))

    results.append(dq.CheckResult("gold_single_source_run_id", LAYER, "CRITICAL", n_source_run_ids == 1,
                                  abs(n_source_run_ids - 1), expected="1", details=f"distinct source_run_id in Silver={n_source_run_ids}"))

    # Product of (1 + r) as exp(sum(log(1 + r))): a set-based product over the months of each ticker-year.
    compounded = (monthly.groupBy("ticker", F.year("month_start").alias("year"))
                  .agg(F.exp(F.sum(F.log1p("monthly_return"))).alias("compound")))
    n_comp_bad = count_where(yearly.join(compounded, ["ticker", "year"], "left"),
                             F.col("compound").isNull()
                             | (F.abs(F.col("compound") - (1 + F.col("yearly_return"))) > TOL_COMPOUND))
    results.append(dq.CheckResult("gold_monthly_compounds_to_yearly", LAYER, "WARN", n_comp_bad == 0, n_comp_bad,
                                  expected=f"0 ticker-years off by > {TOL_COMPOUND}"))

    first_vol = daily.filter(F.col("vol_60d_ann").isNotNull()).groupBy("ticker").agg(F.min("trade_date").alias("first_vol"))
    leading = {r["ticker"]: r["n"] for r in
               daily.filter("volume_status = 'normal'").join(first_vol, "ticker", "left")
                    .filter(F.col("first_vol").isNull() | (F.col("trade_date") < F.col("first_vol")))
                    .groupBy("ticker").agg(F.count(F.lit(1)).alias("n")).collect()}
    off_vol = {t: leading.get(t, 0) for t in configured_tickers if leading.get(t, 0) != N}
    results.append(dq.CheckResult("gold_vol_leading_nulls", LAYER, "WARN", not off_vol, len(off_vol),
                                  expected=f"{N} leading NULL normal rows per ticker", details=f"leading={leading}"))

    partial_months = {r["ticker"]: r["n"] for r in
                      monthly.filter("is_partial").groupBy("ticker").agg(F.count(F.lit(1)).alias("n")).collect()}
    partial_years = {r["ticker"]: r["n"] for r in
                     yearly.filter("is_partial").groupBy("ticker").agg(F.count(F.lit(1)).alias("n")).collect()}
    results.append(dq.CheckResult("gold_partial_periods", LAYER, "INFO", True,
                                  sum(partial_months.values()) + sum(partial_years.values()),
                                  expected="2 partial months and 2 partial years per ticker for the 2026-10-08 snapshot",
                                  details=f"months={partial_months} years={partial_years}"))
    return results, daily_rows

# COMMAND ----------

stats = {"rows_in": None, "rows_out": None, "rows_rejected": None}


def run_gold():
    silver_df = spark.table(silver_table)
    stats["rows_in"] = silver_df.count()

    base = silver.base_date(silver_df, len(configured_tickers))
    if base is None:
        raise RuntimeError("No base date: there is no trade_date on which every ticker has volume_status = 'normal'")

    lineage = silver_df.agg(F.countDistinct("source_run_id").alias("n_ids"),
                            F.min("source_run_id").alias("source_run_id"),
                            F.max("source_ingested_at").alias("source_ingested_at")).first()
    tables = build_gold(silver_df, base, lineage["source_run_id"], lineage["source_ingested_at"])

    results, daily_rows = gold_checks(tables, silver_df, base, lineage["n_ids"])
    dq.write_results(spark, dq_table, results, pipeline_run_id, datetime.now(timezone.utc))

    failed = dq.critical_failures(results)
    if failed:
        raise RuntimeError("Gold CRITICAL checks failed; Gold tables not written: "
                           + "; ".join(f"{r.check_name} ({r.details})" for r in failed))

    # Each overwrite is atomic per table (Delta), but not across the five tables: if the task fails between writes,
    # the Gold tables can briefly come from different runs. Recovery is to rerun this task (full overwrite, DEC-06).
    for name, df in tables.items():
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(gold_tables[name])

    stats["rows_out"] = spark.table(gold_tables["fact_daily_metrics"]).count()
    stats["rows_rejected"] = 0  # Gold rejects nothing; invalid input is stopped by the checks
    return results, base


try:
    check_results, base = run_gold()
except Exception as exc:
    audit.write_audit(spark, audit_table, audit.audit_row(
        pipeline_run_id, TASK_NAME, job_run_id, started_at, datetime.now(timezone.utc), "FAILED",
        stats["rows_in"], stats["rows_out"], stats["rows_rejected"], f"{type(exc).__name__}: {exc}"))
    raise

audit.write_audit(spark, audit_table, audit.audit_row(
    pipeline_run_id, TASK_NAME, job_run_id, started_at, datetime.now(timezone.utc), "SUCCEEDED",
    stats["rows_in"], stats["rows_out"], stats["rows_rejected"]))

# COMMAND ----------

print("base_date =", base, " rows_in =", stats["rows_in"], " rows_out =", stats["rows_out"])
display(spark.table(gold_tables["ticker_summary"]).orderBy("ticker"))
display(spark.table(gold_tables["fact_yearly_metrics"]).select("ticker", "year", "yearly_return", "is_partial")
        .orderBy("ticker", "year"))
for r in check_results:
    print(f"  [{r.severity:8}] {r.check_name:34} {'PASS' if r.passed else 'FAIL'}  failing={r.failing_count}  {r.details}")
print("GOLD PASS")
