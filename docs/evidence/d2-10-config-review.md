# D2-10 Configuration and secrets review

> Performed by the coding agent on 2026-10-10 (about 11:30–12:00 UTC+07) on the local repository, after commit `353b768` plus the changes staged with
> this review. Static review only: no Databricks access. Covers REQ-14 and ENG-08.

## What was checked

1. **Where environment values come from.** I scanned every tracked file outside `config/`, `sql/validation/`, `docs/` and `jobs/` for the catalog literal
   `workspace` and for `/Volumes` paths:
   - `notebooks/00_setup.py`: `f"/Volumes/{catalog}/{bronze_schema}/{cfg['landing_volume']}"`, built from config values.
   - `src/bank_pipeline/fixtures.py`: `f"/Volumes/{cfg['catalog']}/{cfg['schemas']['bronze']}/{FIXTURE_VOLUME}/{name}"`. The fixture path is derived from
     the catalog; `tests/test_pure.py` asserts it changes with a catalog override.
   - No other occurrence.
2. **Other environment literals in code** (`src/`, `notebooks/`, `config/`): URLs, `/Workspace`, `/Users/`, `/home/`, `dbfs:`. The only hits are the
   default `landing_path` in `config/pipeline.json` (by design) and a docstring in `bronze.py` that mentions the `dbfs:` prefix.
3. **Hard-coded table names in code:** no schema-qualified table strings (`'bronze.…'`, `'silver.…'`, …) in `src/` or `notebooks/`. All table names go
   through `config.table_name(cfg, layer, name)`.
4. **Overrides:** the Job parameters `catalog` and `landing_path` (`jobs/indonesia_bank_stocks_pipeline.job.yml`) and the notebook widgets override
   `config/pipeline.json` via `load_config`. The catalog name is validated as an identifier before it is used in SQL; that validation rejected the
   misentered path in D2-09 runs 268776281869222 and 844273765778101.
5. **Literal catalog in SQL files:** the `sql/validation/*.sql` files use `workspace.*` literally. Each file now says so in its header and explains
   how to adapt it for another catalog.
6. **Secret, email and host scan over all tracked files** (`git ls-files` plus the staged files of this change: 42 files). Patterns: email addresses; `dapi…`,
   `ghp_…`, `github_pat_`, `AKIA…`, `xox?-`, `kgat_`; private-key headers; `*.cloud.databricks.com` and `*.azuredatabricks.net` workspace hosts;
   `dbc-…` workspace prefixes; the local user name and the GitHub account name; `/home/`.
7. **Keyword hits** for `token`, `password`, `secret`, `api_key`, `KAGGLE_KEY` and `KAGGLE_API_TOKEN`, classified by hand.
8. **`.gitignore` effectiveness:** `git status --ignored` and a check that no ignored path is tracked.
9. **Credentials:** the pipeline reads only files from a Unity Catalog Volume and uses no credentials, so no secret scope is required
   (`docs/evidence/d1-02-workspace-capabilities.md`, DEC-07).

## Findings

| # | Finding | Severity | Action |
| - | ------- | -------- | ------ |
| 1 | No code hard-codes the catalog, schemas, landing path, workspace URL or user path | — | None |
| 2 | `sql/validation/*.sql` use `workspace.*` literally without saying so | Low (documentation) | Fixed: header note in all four files |
| 3 | Secret, email, host and user-path scan: **0 matches** in all files except this one, whose lines 14 and 24–25 list the scan patterns themselves (pattern names, no values) | — | None |
| 4 | Keyword hits are explanatory text or ignore patterns only: `.gitignore` lines 9, 14, 19; `docs/DATASET.md:200` (names of Kaggle auth options, no values); `docs/TEST_STRATEGY.md` ("Databricks Connect would need a token"); `docs/evidence/d1-02-workspace-capabilities.md` (the "Secret scopes" row) | — | None |
| 5 | `git status --ignored` lists the raw-data folder, the local planning and AI-assistant files and the third-party reference docs as ignored; none of them is tracked | — | None |
| 6 | The Job YAML contains only the placeholders `<your-email>` and `<your-user>` | — | None |

## Result

**Clean.** Environment values come only from `config/pipeline.json`, Job parameters or widgets; no secrets, emails, workspace hosts or real user paths are
tracked; the ignore rules work. REQ-14 and ENG-08 are satisfied.
