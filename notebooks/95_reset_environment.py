# Databricks notebook source
# MAGIC %md
# MAGIC # 95 Reset environment (D3-04 clean-state run)
# MAGIC **Destructive.** Drops every Bronze, Silver, Gold and `ops` table listed in `docs/DATA_MODEL.md` so the Job can be shown to rebuild everything
# MAGIC from the landed files. Schemas and Volumes are **not** dropped: the landing files and test fixtures stay. The `ops` history (run audit,
# MAGIC DQ results) is deleted too; the recorded evidence lives in `docs/evidence/`. Does nothing unless the widget `confirm` is exactly `RESET`.
# MAGIC Procedure: `docs/RUNBOOK.md`. Not yet run in Databricks.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog (empty = config)")
dbutils.widgets.text("confirm", "", "Type RESET to drop all pipeline tables")

# COMMAND ----------

import os
import sys

# Same bootstrap as the pipeline notebooks (import via sys.path verified in D1-10).
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from bank_pipeline.config import find_repo_root, load_config
from bank_pipeline.reset import is_confirmed, tables_to_drop

repo_root = find_repo_root(os.getcwd())
cfg = load_config(repo_root, {"catalog": dbutils.widgets.get("catalog")})
tables = tables_to_drop(cfg)
print(f"catalog={cfg['catalog']}\nTables in scope ({len(tables)}):")
for t in tables:
    print("  ", t)

# COMMAND ----------

if not is_confirmed(dbutils.widgets.get("confirm")):
    print("NOT CONFIRMED: nothing was dropped. Set the widget confirm = RESET to proceed.")
    dbutils.notebook.exit("NOT CONFIRMED")

# COMMAND ----------

dropped, absent = [], []
for t in tables:
    # tableExists is checked first only to report what was there; DROP ... IF EXISTS is safe either way.
    (dropped if spark.catalog.tableExists(t) else absent).append(t)
    spark.sql(f"DROP TABLE IF EXISTS {t}")

print(f"Dropped ({len(dropped)}):", *dropped, sep="\n  ")
print(f"Already absent ({len(absent)}):", *absent, sep="\n  ")
print("Schemas and Volumes were kept. Next: run the Job with its default parameters (docs/RUNBOOK.md).")
print("RESET DONE")
