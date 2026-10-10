"""Clean-state reset for the D3-04 reproducibility run (docs/RUNBOOK.md, "Reset for a clean-state run"). Plain Python, no Spark."""
from bank_pipeline.config import table_name

# Every table in docs/DATA_MODEL.md, in drop order (Gold first, ops last). Schemas and Volumes are deliberately not listed:
# the landed files stay in place, so the next Job run rebuilds everything from them, and 00_setup recreates the ops tables.
RESET_TABLES = (
    ("gold", "ticker_summary"),
    ("gold", "fact_yearly_metrics"),
    ("gold", "fact_monthly_metrics"),
    ("gold", "fact_daily_metrics"),
    ("gold", "dim_ticker"),
    ("silver", "daily_prices_quarantine"),
    ("silver", "daily_prices"),
    ("bronze", "source_run_summary"),
    ("bronze", "daily_prices_raw"),
    ("ops", "dq_results"),
    ("ops", "run_audit"),
)

CONFIRM_WORD = "RESET"


def tables_to_drop(cfg):
    """Fully qualified names of the tables the reset notebook drops, built from the config catalog and schemas."""
    return [table_name(cfg, layer, name) for layer, name in RESET_TABLES]


def is_confirmed(value):
    """Only the exact word RESET (surrounding spaces ignored) confirms the destructive reset."""
    return (value or "").strip() == CONFIRM_WORD
