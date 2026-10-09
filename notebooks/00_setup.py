# Databricks notebook source
# MAGIC %md
# MAGIC # 00 Setup (D1-10)
# MAGIC Creates the schemas, the landing Volume and the `ops` tables. Idempotent: safe to run repeatedly.
# MAGIC Design: `docs/DATA_MODEL.md` §0–§3. Not yet run in Databricks.

# COMMAND ----------

# Empty widget = use the value from config/pipeline.json. Job parameters with the same names override these.
dbutils.widgets.text("catalog", "", "Catalog (empty = config)")
dbutils.widgets.text("landing_path", "", "Landing path (empty = config)")

# COMMAND ----------

import os
import sys

# bank_pipeline lives in <repo>/src and this notebook in <repo>/notebooks, so the package has to be put on
# sys.path before find_repo_root can be imported. Importing .py files from a Git folder on serverless is the
# DEC-10 assumption to verify here; if it fails, fall back to %run of a functions notebook.
_src_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from bank_pipeline.config import find_repo_root, load_config, table_name

repo_root = find_repo_root(os.getcwd())
assert os.path.realpath(_src_dir) == os.path.realpath(repo_root / "src"), f"Unexpected layout: {_src_dir} vs {repo_root / 'src'}"

cfg = load_config(repo_root, {
    "catalog": dbutils.widgets.get("catalog"),
    "landing_path": dbutils.widgets.get("landing_path"),
})
catalog = cfg["catalog"]
print(f"repo_root={repo_root}  catalog={catalog}  landing_path={cfg['landing_path']}")

# COMMAND ----------

# IF NOT EXISTS keeps reruns harmless (DEC-06 full refresh applies to tables, not to this structure).
for schema in cfg["schemas"].values():
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

bronze_schema = cfg["schemas"]["bronze"]
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`{bronze_schema}`.`{cfg['landing_volume']}`")

# COMMAND ----------

# Column types follow docs/DATA_MODEL.md §3. Both tables are append-only, keyed by (pipeline_run_id, task_name/check_name).
run_audit = table_name(cfg, "ops", "run_audit")
dq_results = table_name(cfg, "ops", "dq_results")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {run_audit} (
  pipeline_run_id STRING,
  task_name       STRING,
  job_run_id      STRING,
  started_at      TIMESTAMP,
  ended_at        TIMESTAMP,
  status          STRING,
  rows_in         BIGINT,
  rows_out        BIGINT,
  rows_rejected   BIGINT,
  error_message   STRING
) USING DELTA
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {dq_results} (
  pipeline_run_id STRING,
  check_name      STRING,
  layer           STRING,
  severity        STRING,
  passed          BOOLEAN,
  failing_count   BIGINT,
  expected        STRING,
  details         STRING,
  checked_at      TIMESTAMP
) USING DELTA
""")

# COMMAND ----------

existing_schemas = {row[0] for row in spark.sql(f"SHOW SCHEMAS IN `{catalog}`").collect()}
expected_schemas = set(cfg["schemas"].values())

volume_path = f"/Volumes/{catalog}/{bronze_schema}/{cfg['landing_volume']}"
try:
    dbutils.fs.ls(volume_path)
    volume_ok = True
except Exception as exc:  # listing fails if the Volume does not exist or is not accessible
    volume_ok = False
    print(f"Volume check failed: {exc}")

ops_tables = {name: spark.catalog.tableExists(name) for name in (run_audit, dq_results)}

print("Schemas present :", {s: s in existing_schemas for s in sorted(expected_schemas)})
print("Landing volume  :", volume_path, "OK" if volume_ok else "MISSING")
if cfg["landing_path"].rstrip("/") != volume_path:
    print("Note: landing_path is overridden and differs from the Volume path:", cfg["landing_path"])
print("ops tables      :", ops_tables)

setup_ok = expected_schemas <= existing_schemas and volume_ok and all(ops_tables.values())
print("SETUP", "PASS" if setup_ok else "FAIL")
assert setup_ok, "Setup incomplete; see the messages above."
