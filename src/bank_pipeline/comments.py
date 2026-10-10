"""Unity Catalog comments for the Gold tables and their key, KPI and lineage columns (REQ-25).

Plain Python (no Spark): notebooks/03_gold_build.py executes comment_statements(cfg) after the Gold tables are written.
The texts follow docs/KPI_DEFINITIONS.md and docs/DATA_MODEL.md §5.
"""
from bank_pipeline.config import table_name

TABLE_COMMENTS = {
    "dim_ticker": "One row per bank ticker, loaded from config/pipeline.json.",
    "fact_daily_metrics": "Daily KPIs per ticker and trade date from the base date (K1, K3, K4, K6, K10), adjclose-based.",
    "fact_monthly_metrics": "Monthly return and average daily volume per ticker and month (K8, K11), derived from daily data.",
    "fact_yearly_metrics": "Calendar-year return per ticker and year (K9), derived from daily data.",
    "ticker_summary": "Full-period KPIs per ticker since the base date (K2, K5, K7), adjclose-based.",
}

LINEAGE_COMMENTS = {
    "source_run_id": "Run ID of the source snapshot, from run-summary.json.",
    "source_ingested_at": "Latest source ingestion timestamp in the snapshot (max ingested_at_utc of the daily CSVs).",
    "pipeline_run_id": "Pipeline run (Job run ID) that built this table.",
    "built_at": "Time this table was written by the Gold build.",
}

_TICKER = "Bank ticker (BBCA, BBNI, BMRI, BBRI); key."

COLUMN_COMMENTS = {
    "dim_ticker": {
        "ticker": _TICKER,
        **LINEAGE_COMMENTS,
    },
    "fact_daily_metrics": {
        "ticker": "Bank ticker; key with trade_date.",
        "trade_date": "Trading date from the base date onwards; key with ticker.",
        "volume_status": "normal, zero_all_tickers (all four banks show zero volume) or zero_partial (zero volume while another bank traded); flagged rows are kept.",
        "normalized_index": "K1: 100 x adjclose / adjclose on the base date.",
        "daily_return": "K3: simple adjclose return vs the previous normal row; NULL on flagged rows and on the base date.",
        "vol_60d_ann": "K4: sample std. dev. of the last 60 normal-row returns x sqrt(252); NULL until 60 returns exist and on flagged rows.",
        "running_peak": "Highest adjclose from the base date to this date (all rows).",
        "drawdown": "K6: adjclose / running_peak - 1, always <= 0.",
        "rel_volume_60d": "K10: volume / mean volume of the previous 60 normal rows; NULL until available and on flagged rows.",
        **LINEAGE_COMMENTS,
    },
    "fact_monthly_metrics": {
        "ticker": "Bank ticker; key with month_start.",
        "month_start": "First day of the calendar month; key with ticker.",
        "monthly_return": "K8: month-end adjclose / previous month-end adjclose - 1; the first month starts from the base date.",
        "avg_daily_volume": "K11: mean daily volume over the normal sessions of the month.",
        "is_partial": "TRUE for the first month and for a month still running at the last trade date.",
        **LINEAGE_COMMENTS,
    },
    "fact_yearly_metrics": {
        "ticker": "Bank ticker; key with year.",
        "year": "Calendar year; key with ticker.",
        "yearly_return": "K9: year-end adjclose / previous year-end adjclose - 1; the first year starts from the base date.",
        "is_partial": "TRUE for the first year and for a year still running at the last trade date.",
        **LINEAGE_COMMENTS,
    },
    "ticker_summary": {
        "ticker": _TICKER,
        "total_return": "K2: last adjclose / base-date adjclose - 1 (total return).",
        "vol_full_ann": "K5: sample std. dev. of all normal-row daily returns x sqrt(252).",
        "max_drawdown": "K7: deepest drawdown (minimum of drawdown) since the base date.",
        "peak_date": "K7: day the peak before the deepest drawdown was set (DEC-14).",
        "trough_date": "K7: day of the deepest drawdown (earliest if tied).",
        "current_drawdown": "K7: drawdown on the last trade date.",
        "base_date": "First date on which all four banks traded; start of every return.",
        "last_trade_date": "Last trade date in the snapshot.",
        **LINEAGE_COMMENTS,
    },
}


def sql_string(text):
    """Spark SQL string literal: backslash and single quote are backslash-escaped (two adjacent literals would be concatenated)."""
    return "'" + str(text).replace("\\", "\\\\").replace("'", "\\'") + "'"


def comment_statements(cfg):
    """COMMENT ON TABLE and ALTER COLUMN ... COMMENT statements for every Gold table, table names from the config."""
    statements = []
    for name, text in TABLE_COMMENTS.items():
        table = table_name(cfg, "gold", name)
        statements.append(f"COMMENT ON TABLE {table} IS {sql_string(text)}")
        for column, column_text in COLUMN_COMMENTS[name].items():
            statements.append(f"ALTER TABLE {table} ALTER COLUMN `{column}` COMMENT {sql_string(column_text)}")
    return statements
