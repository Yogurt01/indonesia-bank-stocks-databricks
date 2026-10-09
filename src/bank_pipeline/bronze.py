"""Pure helpers for the Bronze ingestion notebook (no Spark)."""

# Output column order (docs/DATA_MODEL.md §1). _rescued_data stays last so the typed source columns read naturally.
DAILY_PRICES_RAW_COLUMNS = (
    "source_date", "open", "high", "low", "close", "adjclose", "volume", "ingested_at_utc",
    "ticker", "source_file", "bronze_loaded_at", "pipeline_run_id", "_rescued_data",
)
SOURCE_RUN_SUMMARY_COLUMNS = (
    "ticker", "source_symbol", "stock", "source_run_id", "daily_rows", "daily_date_max",
    "daily_duplicate_dates", "raw_json", "source_file", "bronze_loaded_at", "pipeline_run_id",
)


def folder_from_path(path):
    """Landing folder of a file, e.g. '.../landing/bbca/BBCA.JK.csv' -> 'bbca' (scheme prefixes like dbfs: are harmless)."""
    parts = [p for p in str(path).split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Path has no parent folder: {path!r}")
    return parts[-2]


def ticker_for_folder(cfg, folder):
    """Project ticker for a landing folder; an unexpected folder is an error, not a silently dropped file."""
    mapping = {t["folder"]: t["ticker"] for t in cfg["tickers"]}
    if folder not in mapping:
        raise ValueError(f"Unknown landing folder {folder!r}; expected one of {sorted(mapping)}")
    return mapping[folder]


def header_matches(header_line, expected_columns):
    """Exact name-and-order comparison of a raw CSV header line (tolerates a BOM and a trailing CR)."""
    if header_line is None:
        return False
    columns = header_line.lstrip("﻿").rstrip("\r\n").split(",")
    return columns == list(expected_columns)
