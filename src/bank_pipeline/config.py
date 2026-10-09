"""Pipeline configuration helpers.

Kept free of Spark imports so the functions can be checked with plain Python.
"""
import json
import re
from pathlib import Path

CONFIG_RELATIVE_PATH = Path("config") / "pipeline.json"

# Only these keys may be overridden by Job parameters or notebook widgets.
OVERRIDABLE_KEYS = ("catalog", "landing_path")

# The catalog name is interpolated into SQL, so reject anything that is not a plain identifier.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def find_repo_root(start_dir):
    """Walk up from start_dir until a directory containing config/pipeline.json is found."""
    start = Path(start_dir).resolve()
    for candidate in (start, *start.parents):
        if (candidate / CONFIG_RELATIVE_PATH).is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not find {CONFIG_RELATIVE_PATH} in {start} or any parent directory. "
        "Run the notebook from inside the repository (for example a Databricks Git folder)."
    )


def load_config(repo_root, overrides=None):
    """Load config/pipeline.json; non-empty override values replace catalog and landing_path."""
    with open(Path(repo_root) / CONFIG_RELATIVE_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    for key in OVERRIDABLE_KEYS:
        value = (overrides or {}).get(key)
        # Empty widgets arrive as "", which means "use the config file value".
        if value is not None and str(value).strip():
            cfg[key] = str(value).strip()
    if not _IDENTIFIER.match(cfg["catalog"]):
        raise ValueError(f"Invalid catalog name: {cfg['catalog']!r}")
    return cfg


def table_name(cfg, layer, name):
    """Return the three-part name <catalog>.<schema>.<name> for a layer (bronze, silver, gold, ops)."""
    if layer not in cfg["schemas"]:
        raise KeyError(f"Unknown layer {layer!r}; expected one of {sorted(cfg['schemas'])}")
    return f"{cfg['catalog']}.{cfg['schemas'][layer]}.{name}"
