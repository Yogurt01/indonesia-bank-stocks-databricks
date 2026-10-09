# D1-10 Databricks environment setup (owner-reported)

> Run by the owner on 2026-10-09 at about 23:18 (UTC+07): notebook `notebooks/00_setup` from the Databricks Git folder
> (`/Workspace/Users/<user>/indonesia-bank-stocks-databricks`) on serverless compute. Results are owner-reported; the coding agent has
> no Databricks access and has not independently verified them.

## Output (as reported)

```
Schemas present : bronze, gold, ops, silver: all True
Landing volume  : /Volumes/workspace/bronze/landing OK
ops tables      : workspace.ops.run_audit True, workspace.ops.dq_results True
SETUP PASS
```

## What this verifies

- Notebooks from a Git folder run on serverless compute.
- `src/bank_pipeline` imports from the Git folder via `sys.path`. **The DEC-10 import assumption is verified**, so the `%run` fallback is not needed.
- `config/pipeline.json` is readable from the notebook.
- `os.getcwd()` resolves inside the Git folder (`find_repo_root` succeeded).
- The schemas `bronze`, `silver`, `gold` and `ops`, the managed Volume `workspace.bronze.landing`, and the tables `ops.run_audit` and `ops.dq_results`
  exist after the run.

## Not verified by this run

- Idempotency on repeated runs. The notebook uses `IF NOT EXISTS`, but a second run was not reported.
- Running the notebook as a Job task, and the `{{job.run_id}}` parameter.
