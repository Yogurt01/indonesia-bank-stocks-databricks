"""Gold KPI tables (docs/KPI_DEFINITIONS.md K1-K11, docs/DATA_MODEL.md §4).

pyspark is imported inside the functions so the module (and its column lists) import without Spark.
All functions work on Silver rows with trade_date >= base_date only.
"""
import math

LINEAGE_COLUMNS = ("source_run_id", "source_ingested_at", "pipeline_run_id", "built_at")

# Column order as in docs/DATA_MODEL.md §4, lineage last.
DIM_TICKER_COLUMNS = ("ticker", "bank_name", "short_name") + LINEAGE_COLUMNS
DAILY_COLUMNS = ("ticker", "trade_date", "close", "adjclose", "volume", "volume_status", "normalized_index",
                 "daily_return", "vol_60d_ann", "running_peak", "drawdown", "rel_volume_60d", "year", "month") + LINEAGE_COLUMNS
MONTHLY_COLUMNS = ("ticker", "month_start", "monthly_return", "avg_daily_volume", "n_sessions",
                   "n_normal_sessions", "is_partial") + LINEAGE_COLUMNS
YEARLY_COLUMNS = ("ticker", "year", "yearly_return", "n_sessions", "is_partial") + LINEAGE_COLUMNS
SUMMARY_COLUMNS = ("ticker", "total_return", "vol_full_ann", "max_drawdown", "peak_date", "trough_date",
                   "current_drawdown", "base_date", "last_trade_date") + LINEAGE_COLUMNS

TABLE_KEYS = {
    "dim_ticker": ("ticker",),
    "fact_daily_metrics": ("ticker", "trade_date"),
    "fact_monthly_metrics": ("ticker", "month_start"),
    "fact_yearly_metrics": ("ticker", "year"),
    "ticker_summary": ("ticker",),
}


def _base_prices(daily_or_silver, base_date):
    """adjclose on the base date per ticker (the denominator of K1, K2 and the first K8/K9 period)."""
    from pyspark.sql import functions as F

    return (daily_or_silver.filter(F.col("trade_date") == F.lit(base_date))
            .select("ticker", F.col("adjclose").alias("base_adjclose")))


def build_daily(silver, base_date, vol_window, rel_volume_window, annualization_factor):
    """fact_daily_metrics without lineage columns: K1, K3, K4, K6, K10."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    rows = silver.filter(F.col("trade_date") >= F.lit(base_date))
    by_date = Window.partitionBy("ticker").orderBy("trade_date")

    # K3, K4 and K10 are defined on normal rows only (G5). A window cannot skip flagged rows, so these are computed on
    # the normal-only rows and joined back; flagged rows then get NULL instead of an artificial 0% return.
    normal = rows.filter(F.col("volume_status") == "normal").select("ticker", "trade_date", "adjclose", "volume")
    normal = normal.withColumn("daily_return", F.col("adjclose") / F.lag("adjclose").over(by_date) - 1)
    vol_win = by_date.rowsBetween(-(vol_window - 1), 0)
    rel_win = by_date.rowsBetween(-rel_volume_window, -1)
    normal_metrics = normal.select(
        "ticker", "trade_date", "daily_return",
        # NULL until the window holds vol_window non-NULL returns (the base-date return is NULL, so 60 leading NULLs).
        F.when(F.count("daily_return").over(vol_win) == vol_window,
               F.stddev_samp("daily_return").over(vol_win) * math.sqrt(annualization_factor)).alias("vol_60d_ann"),
        # Excludes day t; NULL until rel_volume_window previous normal rows exist.
        F.when(F.count("volume").over(rel_win) == rel_volume_window,
               F.col("volume") / F.avg("volume").over(rel_win)).alias("rel_volume_60d"),
    )

    peak_win = by_date.rowsBetween(Window.unboundedPreceding, Window.currentRow)
    return (rows.join(_base_prices(rows, base_date), "ticker", "left")
            .join(normal_metrics, ["ticker", "trade_date"], "left")
            .withColumn("normalized_index", 100 * F.col("adjclose") / F.col("base_adjclose"))
            .withColumn("running_peak", F.max("adjclose").over(peak_win))
            .withColumn("drawdown", F.col("adjclose") / F.col("running_peak") - 1)
            .withColumn("year", F.year("trade_date"))
            .withColumn("month", F.month("trade_date"))
            .select(*[c for c in DAILY_COLUMNS if c not in LINEAGE_COLUMNS]))


def _last_weekday(period_end_col):
    """Last Monday-Friday on or before a period end date (dayofweek: 1 = Sunday, 7 = Saturday)."""
    from pyspark.sql import functions as F

    dow = F.dayofweek(period_end_col)
    return (F.when(dow == 7, F.date_sub(period_end_col, 1))
             .when(dow == 1, F.date_sub(period_end_col, 2))
             .otherwise(period_end_col))


def _period_returns(daily, base_date, period_col, period_end_expr):
    """Shared K8/K9 logic: period return from period-end adjclose, first period starting at the base-date adjclose.

    is_partial: TRUE for each ticker's first period (it starts at the base date) and for the period containing the dataset's
    last trade_date when that date is earlier than the period's last weekday (an exchange holiday on that weekday would
    therefore mark a complete final period as partial; conservative).
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    last_date = daily.agg(F.max("trade_date").alias("dataset_last_date"))
    periods = (daily.groupBy("ticker", period_col)
               .agg(F.max_by("adjclose", "trade_date").alias("end_adjclose"),
                    F.count(F.lit(1)).alias("n_sessions"),
                    F.sum(F.when(F.col("volume_status") == "normal", 1).otherwise(0)).alias("n_normal_sessions"),
                    F.avg(F.when(F.col("volume_status") == "normal", F.col("volume"))).alias("avg_daily_volume"),
                    F.max("trade_date").alias("period_last_date")))
    by_period = Window.partitionBy("ticker").orderBy(period_col)
    prev_end = F.lag("end_adjclose").over(by_period)
    is_first = F.row_number().over(by_period) == 1
    running = ((F.col("period_last_date") == F.col("dataset_last_date"))
               & (F.col("dataset_last_date") < _last_weekday(period_end_expr)))
    return (periods.join(_base_prices(daily, base_date), "ticker", "left")
            .crossJoin(F.broadcast(last_date))
            .withColumn("period_return", F.col("end_adjclose") / F.coalesce(prev_end, F.col("base_adjclose")) - 1)
            .withColumn("is_partial", is_first | running))


def build_monthly(daily, base_date):
    """fact_monthly_metrics without lineage columns: K8, K11."""
    from pyspark.sql import functions as F

    with_month = daily.withColumn("month_start", F.trunc("trade_date", "MM"))
    out = _period_returns(with_month, base_date, "month_start", F.last_day("month_start"))
    return (out.withColumnRenamed("period_return", "monthly_return")
            .select(*[c for c in MONTHLY_COLUMNS if c not in LINEAGE_COLUMNS]))


def build_yearly(daily, base_date):
    """fact_yearly_metrics without lineage columns: K9."""
    from pyspark.sql import functions as F

    # SQL make_date (Spark 3.0+) rather than F.make_date, which only exists in PySpark 3.5+.
    out = _period_returns(daily, base_date, "year", F.expr("make_date(year, 12, 31)"))
    return (out.withColumnRenamed("period_return", "yearly_return")
            .select(*[c for c in YEARLY_COLUMNS if c not in LINEAGE_COLUMNS]))


def build_summary(daily, base_date, annualization_factor):
    """ticker_summary without lineage columns: K2, K5, K7.

    trough_date = date of max_drawdown (earliest if tied).
    peak_date (DEC-14) = earliest trade_date <= trough_date whose adjclose equals the running_peak at trough_date, i.e. the day the
    peak was set. Flat carry-forward rows (holidays) that sit at the peak afterwards are therefore never reported as the peak date.
    """
    from pyspark.sql import functions as F

    per_ticker = (daily.groupBy("ticker")
                  .agg(F.max_by("adjclose", "trade_date").alias("last_adjclose"),
                       (F.stddev_samp("daily_return") * math.sqrt(annualization_factor)).alias("vol_full_ann"),
                       F.min("drawdown").alias("max_drawdown"),
                       F.max_by("drawdown", "trade_date").alias("current_drawdown"),
                       F.max("trade_date").alias("last_trade_date"))
                  .join(_base_prices(daily, base_date), "ticker", "left")
                  .withColumn("total_return", F.col("last_adjclose") / F.col("base_adjclose") - 1))

    # max_drawdown is min() of the same column, so the equality below compares identical doubles.
    trough = (daily.join(per_ticker.select("ticker", "max_drawdown"), "ticker")
              .filter(F.col("drawdown") == F.col("max_drawdown"))
              .groupBy("ticker").agg(F.min("trade_date").alias("trough_date")))
    peak_value = (daily.join(trough, "ticker")
                  .filter(F.col("trade_date") == F.col("trough_date"))
                  .select("ticker", "trough_date", F.col("running_peak").alias("peak_value")))
    # Exact equality is safe: running_peak is max() of adjclose, so it is one of the adjclose doubles, and flat rows carry that
    # identical value. Before the peak was first set, adjclose is strictly below it, so the earliest match is the setting day.
    peak = (daily.join(peak_value, "ticker")
            .filter((F.col("trade_date") <= F.col("trough_date")) & (F.col("adjclose") == F.col("peak_value")))
            .groupBy("ticker").agg(F.min("trade_date").alias("peak_date")))

    return (per_ticker.join(trough, "ticker", "left").join(peak, "ticker", "left")
            .withColumn("base_date", F.lit(base_date).cast("date"))
            .select(*[c for c in SUMMARY_COLUMNS if c not in LINEAGE_COLUMNS]))


def build_dim_ticker(cfg, spark=None):
    """dim_ticker without lineage columns, from config/pipeline.json."""
    if spark is None:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
    rows = [(t["ticker"], t["bank_name"], t["short_name"]) for t in cfg["tickers"]]
    return spark.createDataFrame(rows, "ticker STRING, bank_name STRING, short_name STRING")


def with_lineage(df, source_run_id, source_ingested_at, pipeline_run_id, columns):
    """Add the lineage columns (KPI rule G6) and select the documented column order."""
    from pyspark.sql import functions as F

    return (df.withColumn("source_run_id", F.lit(source_run_id).cast("string"))
              .withColumn("source_ingested_at", F.lit(source_ingested_at).cast("timestamp"))
              .withColumn("pipeline_run_id", F.lit(pipeline_run_id))
              .withColumn("built_at", F.current_timestamp())
              .select(*columns))
