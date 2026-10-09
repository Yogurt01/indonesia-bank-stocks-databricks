"""Test fixtures for the induced-failure test (D2-09, DEC-13 option A). Plain Python, no Spark."""

FIXTURE_VOLUME = "test_fixtures"
FAILURE_FIXTURE_NAME = "failure_dup_key"


def fixture_root(cfg, name=FAILURE_FIXTURE_NAME):
    """Fixture landing path, kept in its own Volume so the real landing Volume is never modified."""
    return f"/Volumes/{cfg['catalog']}/{cfg['schemas']['bronze']}/{FIXTURE_VOLUME}/{name}"


def newline_style(text):
    """The file's line ending, so the rewritten file keeps the original style."""
    return "\r\n" if "\r\n" in text else "\n"


def first_field(line):
    """First CSV field of a line (the Date column of the source CSVs; dates contain no commas or quotes)."""
    return line.split(",", 1)[0]


def replace_row_with_previous(text, row_number):
    """Replace 1-based data row `row_number` (header excluded) with an exact copy of the row before it.

    The row count stays the same, so the Bronze row-count check passes and the duplicate key reaches Silver.
    Returns (new_text, replaced_line, duplicated_line).
    """
    nl = newline_style(text)
    trailing = text.endswith(nl)
    lines = text.split(nl)
    if trailing:
        lines = lines[:-1]  # split() leaves an empty string after the final line ending
    header, data = lines[0], lines[1:]
    if not 2 <= row_number <= len(data):
        raise ValueError(f"row_number must be between 2 and {len(data)} (data rows), got {row_number}")
    replaced, duplicated = data[row_number - 1], data[row_number - 2]
    data[row_number - 1] = duplicated
    new_text = nl.join([header, *data]) + (nl if trailing else "")
    return new_text, replaced, duplicated
