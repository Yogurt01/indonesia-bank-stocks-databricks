"""ops.run_audit rows: one per task run, written on success and on failure.

Spark is imported only inside write_audit, so audit_row can be checked with plain Python.
"""

STATUSES = ("SUCCEEDED", "FAILED")

# Long stack traces add nothing to the audit table; the full error stays in the Job run output.
MAX_ERROR_LENGTH = 2000

# Same order and names as the ops.run_audit DDL in notebooks/00_setup.py (docs/DATA_MODEL.md §3).
AUDIT_COLUMNS = ("pipeline_run_id", "task_name", "job_run_id", "started_at", "ended_at", "status",
                 "rows_in", "rows_out", "rows_rejected", "error_message")


def audit_row(pipeline_run_id, task_name, job_run_id, started_at, ended_at, status,
              rows_in=None, rows_out=None, rows_rejected=None, error_message=None):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    if error_message is not None and len(error_message) > MAX_ERROR_LENGTH:
        error_message = error_message[:MAX_ERROR_LENGTH - 3] + "..."
    return {
        "pipeline_run_id": pipeline_run_id,
        "task_name": task_name,
        # Interactive runs have no Job run; store NULL rather than an empty string.
        "job_run_id": job_run_id or None,
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_rejected": rows_rejected,
        "error_message": error_message,
    }


def write_audit(spark, table, row):
    """Append one audit row to ops.run_audit."""
    from pyspark.sql import types as T

    schema = T.StructType([
        T.StructField("pipeline_run_id", T.StringType()),
        T.StructField("task_name", T.StringType()),
        T.StructField("job_run_id", T.StringType()),
        T.StructField("started_at", T.TimestampType()),
        T.StructField("ended_at", T.TimestampType()),
        T.StructField("status", T.StringType()),
        T.StructField("rows_in", T.LongType()),
        T.StructField("rows_out", T.LongType()),
        T.StructField("rows_rejected", T.LongType()),
        T.StructField("error_message", T.StringType()),
    ])
    spark.createDataFrame([tuple(row[c] for c in AUDIT_COLUMNS)], schema).write.mode("append").saveAsTable(table)
