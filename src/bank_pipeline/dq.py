"""Data-quality check results and their ops.dq_results rows.

Spark is imported only inside write_results, so the rest can be checked with plain Python.
"""
from dataclasses import dataclass

SEVERITIES = ("CRITICAL", "WARN", "INFO")

# Same order and names as the ops.dq_results DDL in notebooks/00_setup.py (docs/DATA_MODEL.md §3).
DQ_COLUMNS = ("pipeline_run_id", "check_name", "layer", "severity", "passed",
              "failing_count", "expected", "details", "checked_at")


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    layer: str
    severity: str
    passed: bool
    failing_count: int
    expected: str = ""
    details: str = ""

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {self.severity!r}")


def to_rows(results, pipeline_run_id, checked_at):
    """Turn CheckResults into dicts matching the ops.dq_results columns."""
    return [
        {
            "pipeline_run_id": pipeline_run_id,
            "check_name": r.check_name,
            "layer": r.layer,
            "severity": r.severity,
            "passed": bool(r.passed),
            "failing_count": int(r.failing_count),
            "expected": r.expected,
            "details": r.details,
            "checked_at": checked_at,
        }
        for r in results
    ]


def critical_failures(results):
    """Failed CRITICAL checks; any entry here must stop the task before it writes its tables."""
    return [r for r in results if r.severity == "CRITICAL" and not r.passed]


def write_results(spark, table, results, pipeline_run_id, checked_at):
    """Append check results to ops.dq_results (append-only history)."""
    from pyspark.sql import types as T

    schema = T.StructType([
        T.StructField("pipeline_run_id", T.StringType()),
        T.StructField("check_name", T.StringType()),
        T.StructField("layer", T.StringType()),
        T.StructField("severity", T.StringType()),
        T.StructField("passed", T.BooleanType()),
        T.StructField("failing_count", T.LongType()),
        T.StructField("expected", T.StringType()),
        T.StructField("details", T.StringType()),
        T.StructField("checked_at", T.TimestampType()),
    ])
    rows = [tuple(row[c] for c in DQ_COLUMNS) for row in to_rows(results, pipeline_run_id, checked_at)]
    spark.createDataFrame(rows, schema).write.mode("append").saveAsTable(table)
