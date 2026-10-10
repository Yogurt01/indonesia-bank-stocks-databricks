"""Rerun (idempotency) check: compare the latest Delta version of a table with the previous one (D2-07, docs/TEST_STRATEGY.md §3).

pyspark is imported inside the Spark functions; pick_versions and evaluate are plain Python.
"""
from functools import reduce

# Doubles from grouped aggregations (e.g. the full-period stddev) can differ in the last bits when Spark combines partial results in a
# different order; window functions ordered within a partition are typically stable. The tolerance covers either case.
DOUBLE_TOLERANCE = 1e-9

# Columns that legitimately change on every run.
RUN_SPECIFIC_COLUMNS = ("pipeline_run_id", "bronze_pipeline_run_id", "bronze_loaded_at", "processed_at",
                        "quarantined_at", "built_at")

# Maintenance and metadata-only operations (e.g. predictive optimization on Unity Catalog managed tables, or the Gold table and
# column comments applied after every build, REQ-25) create versions without new data. Comparing across them would compare a run
# with itself and pass trivially, so they are skipped. CHANGE COLUMN is the expected history name of ALTER COLUMN ... COMMENT (unverified).
MAINTENANCE_PREFIXES = ("OPTIMIZE", "VACUUM", "ANALYZE", "COMPUTE STATS", "SET TBLPROPERTIES", "UNSET TBLPROPERTIES",
                        "UPGRADE PROTOCOL", "FSCK", "REORG", "CLONE", "CHANGE COLUMN")

# (layer, table) -> key columns; None = compare row counts only.
TABLE_KEYS = {
    ("bronze", "daily_prices_raw"): ("ticker", "source_date"),
    ("bronze", "source_run_summary"): ("ticker",),
    ("silver", "daily_prices"): ("ticker", "trade_date"),
    ("silver", "daily_prices_quarantine"): None,
    ("gold", "dim_ticker"): ("ticker",),
    ("gold", "fact_daily_metrics"): ("ticker", "trade_date"),
    ("gold", "fact_monthly_metrics"): ("ticker", "month_start"),
    ("gold", "fact_yearly_metrics"): ("ticker", "year"),
    ("gold", "ticker_summary"): ("ticker",),
}


def pick_versions(history):
    """Given (version, operation) pairs, return (previous, latest) data-writing versions; None where missing."""
    writes = sorted(v for v, op in history if not str(op).upper().startswith(MAINTENANCE_PREFIXES))
    latest = writes[-1] if writes else None
    previous = writes[-2] if len(writes) >= 2 else None
    return previous, latest


def evaluate(metrics, tolerance=DOUBLE_TOLERANCE):
    """PASS only if counts match, keys are unique, no row is missing or different, and doubles are within tolerance."""
    if metrics.get("note"):
        return "FAIL"
    if metrics["rows_prev"] != metrics["rows_latest"]:
        return "FAIL"
    if metrics.get("keys") is None:  # counts-only table
        return "PASS"
    diff = metrics["max_double_diff"]
    ok = (metrics["dup_keys"] == 0 and metrics["missing_rows"] == 0 and metrics["mismatched_non_double"] == 0
          and (diff is None or diff <= tolerance))
    return "PASS" if ok else "FAIL"


def table_history(spark, table):
    """(version, operation) pairs from DESCRIBE HISTORY; the history of a small table is a few rows, so collecting is fine."""
    return [(r["version"], r["operation"]) for r in spark.sql(f"DESCRIBE HISTORY {table}").select("version", "operation").collect()]


def read_version(spark, table, version):
    return spark.sql(f"SELECT * FROM {table} VERSION AS OF {int(version)}")


def compare_versions(prev_df, latest_df, keys, exclude=RUN_SPECIFIC_COLUMNS):
    """Set-based comparison of two versions; returns a dict of metrics (see evaluate)."""
    from pyspark.sql import functions as F
    from pyspark.sql import types as T

    metrics = {"keys": keys, "rows_prev": prev_df.count(), "rows_latest": latest_df.count(), "dup_keys": None,
               "missing_rows": None, "mismatched_non_double": None, "max_double_diff": None, "note": ""}
    if keys is None:
        return metrics

    cols_prev = [c for c in prev_df.columns if c not in exclude]
    cols_latest = [c for c in latest_df.columns if c not in exclude]
    if set(cols_prev) != set(cols_latest):
        metrics["note"] = f"columns differ: only_prev={sorted(set(cols_prev) - set(cols_latest))} only_latest={sorted(set(cols_latest) - set(cols_prev))}"
    cols = [c for c in cols_latest if c in set(cols_prev)]

    metrics["dup_keys"] = latest_df.groupBy(*keys).count().filter(F.col("count") > 1).count()

    doubles = {f.name for f in latest_df.schema.fields if isinstance(f.dataType, (T.DoubleType, T.FloatType))}
    p = prev_df.select(*[F.col(c).alias(f"p_{c}") for c in cols]).withColumn("_in_p", F.lit(True))
    l = latest_df.select(*[F.col(c).alias(f"l_{c}") for c in cols]).withColumn("_in_l", F.lit(True))
    on = reduce(lambda a, b: a & b, [F.col(f"p_{k}").eqNullSafe(F.col(f"l_{k}")) for k in keys])
    joined = p.join(l, on, "full")

    matched = F.col("_in_p").isNotNull() & F.col("_in_l").isNotNull()
    others = [c for c in cols if c not in keys and c not in doubles]
    non_double_diff = reduce(lambda a, b: a | b, [~F.col(f"p_{c}").eqNullSafe(F.col(f"l_{c}")) for c in others], F.lit(False))

    def double_diff(c):
        pc, lc = F.col(f"p_{c}"), F.col(f"l_{c}")
        # NULL equals NULL; NULL against a value is an infinite difference, so it always fails the tolerance.
        return (F.when(pc.isNull() & lc.isNull(), F.lit(0.0))
                 .when(pc.isNull() | lc.isNull(), F.lit(float("inf")))
                 .otherwise(F.abs(pc - lc)))

    dbl = [double_diff(c) for c in cols if c in doubles and c not in keys]
    worst = F.greatest(*dbl) if len(dbl) > 1 else (dbl[0] if dbl else F.lit(None).cast("double"))

    agg = joined.agg(
        F.sum(F.when(~matched, 1).otherwise(0)).alias("missing_rows"),
        F.sum(F.when(matched & non_double_diff, 1).otherwise(0)).alias("mismatched_non_double"),
        F.max(F.when(matched, worst)).alias("max_double_diff"),
    ).first()
    metrics.update(missing_rows=int(agg["missing_rows"] or 0),
                   mismatched_non_double=int(agg["mismatched_non_double"] or 0),
                   max_double_diff=agg["max_double_diff"])
    return metrics
