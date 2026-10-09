"""Silver transformation helpers (docs/DATA_MODEL.md §2, docs/KPI_DEFINITIONS.md G3/G4).

pyspark is imported inside the functions so the module (and its constants) import without Spark.
"""
from functools import reduce
from operator import or_

PRICE_COLUMNS = ("open", "high", "low", "close", "adjclose")
REJECT_REASONS = ("invalid_date", "invalid_price", "non_positive_price", "invalid_volume",
                  "ohlc_inconsistent", "rescued_data_present")
VOLUME_STATUSES = ("normal", "zero_all_tickers", "zero_partial")

# Flat holiday rows should carry the previous value exactly; the tolerance only absorbs floating-point noise
# (prices are float32 values stored as double, so DOUBLE equality is compared with a tolerance, not ==).
TOLERANCE = 1e-6

SILVER_COLUMNS = ("ticker", "trade_date", "open", "high", "low", "close", "adjclose", "volume", "volume_status",
                  "source_ingested_at", "source_file", "source_run_id", "pipeline_run_id", "processed_at")

# Bronze columns as stored, with Bronze's own run ID renamed so it does not clash with the Silver run's pipeline_run_id.
QUARANTINE_COLUMNS = ("source_date", "open", "high", "low", "close", "adjclose", "volume", "ingested_at_utc",
                      "ticker", "source_file", "bronze_loaded_at", "bronze_pipeline_run_id", "_rescued_data",
                      "reject_reason", "pipeline_run_id", "quarantined_at")


def parse_bronze(df):
    """Add a struct column `p` with the typed values; the original Bronze strings stay untouched for quarantine."""
    from pyspark.sql import functions as F

    # try_cast, not cast/to_date: serverless runs with ANSI mode, where a plain cast raises on bad input.
    # A NULL result is then reported by reject_reasons instead of failing the whole task.
    typed = [F.expr("try_cast(source_date AS DATE)").alias("trade_date")]
    typed += [F.expr(f"try_cast(`{c}` AS DOUBLE)").alias(c) for c in PRICE_COLUMNS]
    typed += [F.expr("try_cast(volume AS BIGINT)").alias("volume"),
              F.expr("try_cast(ingested_at_utc AS TIMESTAMP)").alias("source_ingested_at")]
    return df.withColumn("p", F.struct(*typed))


def reject_reasons(df):
    """Add `reject_reasons` (array of codes) and `reject_reason` (codes joined by ';'); an empty array means valid."""
    from pyspark.sql import functions as F

    def p(c):
        return F.col(f"p.{c}")

    def flag(condition):
        # Comparisons with NULL yield NULL; treat that as "rule not violated" (NULLs have their own codes).
        return F.coalesce(condition, F.lit(False))

    rules = {
        "invalid_date": p("trade_date").isNull(),
        "invalid_price": reduce(or_, [p(c).isNull() for c in PRICE_COLUMNS]),
        "non_positive_price": flag(reduce(or_, [p(c) <= 0 for c in PRICE_COLUMNS])),
        "invalid_volume": p("volume").isNull() | flag(p("volume") < 0),
        "ohlc_inconsistent": flag((p("low") > F.least(p("open"), p("close")))
                                  | (p("high") < F.greatest(p("open"), p("close")))),
        "rescued_data_present": F.col("_rescued_data").isNotNull(),
    }
    codes = F.array(*[F.when(rules[code], F.lit(code)) for code in REJECT_REASONS])
    return (df.withColumn("reject_reasons", F.filter(codes, lambda c: c.isNotNull()))
              .withColumn("reject_reason", F.concat_ws(";", "reject_reasons")))


def duplicate_keys(df_valid):
    """(ticker, trade_date) keys occurring more than once, with their count.

    Duplicates are not quarantined: they mean the source snapshot is broken, so a CRITICAL check stops the run.
    """
    from pyspark.sql import functions as F

    return df_valid.groupBy("ticker", "trade_date").count().filter(F.col("count") > 1)


def add_volume_status(df_valid):
    """volume_status per G4, derived from the data on each date (no hard-coded dates)."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    tickers_trading = F.sum(F.when(F.col("volume") > 0, 1).otherwise(0)).over(Window.partitionBy("trade_date"))
    return df_valid.withColumn(
        "volume_status",
        F.when(F.col("volume") > 0, "normal")
         .when(tickers_trading == 0, "zero_all_tickers")
         .otherwise("zero_partial"),
    )


def base_date(df_silver, n_tickers):
    """Earliest trade_date on which all n_tickers have volume_status = 'normal' (G3); None if there is none."""
    from pyspark.sql import functions as F

    row = (df_silver.groupBy("trade_date")
           .agg(F.sum(F.when(F.col("volume_status") == "normal", 1).otherwise(0)).alias("n_normal"))
           .filter(F.col("n_normal") == n_tickers)
           .agg(F.min("trade_date").alias("base_date"))
           .first())
    return row["base_date"] if row else None


def _close_enough(a, b):
    from pyspark.sql import functions as F

    return F.abs(a - b) <= TOLERANCE


def zero_volume_not_flat(df_silver):
    """Zero-volume rows that are not flat: OHLC not all equal, or close differs from the previous row's close."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    prev_close = F.lag("close").over(Window.partitionBy("ticker").orderBy("trade_date"))
    flat = (_close_enough(F.col("open"), F.col("high")) & _close_enough(F.col("high"), F.col("low"))
            & _close_enough(F.col("low"), F.col("close")))
    carried = prev_close.isNull() | _close_enough(F.col("close"), prev_close)  # the first row only needs to be flat
    return df_silver.withColumn("_ok", flat & carried).filter((F.col("volume") == 0) & ~F.col("_ok")).drop("_ok")


def flat_rows_adjclose_not_carried(df_silver):
    """Zero-volume rows whose adjclose differs from the previous row's adjclose (the first row is exempt)."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    prev_adj = F.lag("adjclose").over(Window.partitionBy("ticker").orderBy("trade_date"))
    return (df_silver.withColumn("prev_adjclose", prev_adj)
            .filter((F.col("volume") == 0) & F.col("prev_adjclose").isNotNull()
                    & ~_close_enough(F.col("adjclose"), F.col("prev_adjclose"))))
