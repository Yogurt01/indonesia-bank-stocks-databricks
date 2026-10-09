# D1-02 Databricks workspace capability check (owner-reported)

> Performed by the owner in the Databricks web UI on 2026-10-09. Results are owner-reported; screenshots are held by the owner
> and not stored in the repo. The coding agent has not independently verified them. All test objects used a sandbox schema and
> were removed (see [Cleanup](#cleanup-owner-reported-no-screenshots)).

| Capability | Status | Observation | Limits / not tested |
| ---------- | ------ | ----------- | ------------------- |
| Workspace type | Verified | Databricks Free Edition on AWS (host suffix cloud.databricks.com); sign-in by email with a verification code; no banner. A "Verify identity" button is visible and was not used. | Edition limits per Databricks docs (see below) |
| Compute | Limited | Compute page shows only serverless (Default Interactive Compute, Default Automated Compute); no option to create a cluster. SQL warehouse: only "Serverless Starter Warehouse" (2X-Small); "Create SQL warehouse" is disabled. | Serverless only; no custom clusters |
| Unity Catalog | Verified | Catalog `workspace` (schemas `default`, `information_schema`), `system`, and `samples` (shared). Creating schema `sandbox_test` succeeded. | Catalog creation not tested |
| Volume | Verified | Managed volume `raw_files` created at `/Volumes/workspace/sandbox_test/raw_files`. | None |
| Notebook (Python and SQL) | Verified | A Python cell and two `%sql` cells ran on serverless compute. | Other languages not tried (Scala and R are unsupported on serverless per docs) |
| CSV upload and Spark read | Verified | A 3-row test CSV (77 B) uploaded to the Volume; `spark.read.csv` returned 3 rows with date/string/integer columns. | Only a tiny test file; the real daily CSVs and the Parquet `TIMESTAMP(NANOS)` column were not tested |
| Delta table and SQL | Verified | `saveAsTable` succeeded; `SELECT` returned 3 rows; `DESCRIBE DETAIL` reported `format = delta`. | None |
| Jobs | Verified (single task) | A Job with one notebook task ran twice, both Succeeded (1m 11s and 23s); the Job compute shows Serverless. | Multi-task dependencies, retries and failure notifications not tested |
| Job schedule | Partly verified | A schedule (09:37 PM UTC+07:00) saved and appeared in Schedules & Triggers. | Automatic firing at the scheduled time not observed |
| AI/BI dashboard | Verified | Dashboard `sandbox_test_dash` created; a line chart on the test table matched the data. | Publish and sharing not tested |
| Git folder | Verified (public clone) | A Git folder was created from the public repo `octocat/Hello-World`; branch `master`, `.git` and README visible; no authentication needed. | Push, pull from this project's repo, private repos, and a Job running a notebook from a Git folder not tested |
| Secret scopes | Not tested | Not required: the pipeline uses manually downloaded files and no credentials. | Revisit only if a credential is introduced |
| Quotas | Not measured | Not visible in the UI during the check. | See the docs-based limits below |

## Cleanup (owner-reported, no screenshots)

The Git folder, dashboard, Job, schedule and schema `sandbox_test` were deleted.
Deletion of the test notebook `sandbox_test_nb` is **NOT confirmed**.

## Documented Free Edition and serverless limits (cross-checked by the advisory chat on 2026-10-09; not re-verified by the coding agent)

- Free Edition provides serverless compute only; serverless notebook compute has limited size and usage.
- If the quota is exceeded, compute is shut down for the rest of the day (in extreme cases the month); data and settings are kept.
- Jobs: at most 5 concurrent job tasks per account.
- Free Edition is for non-commercial use, has no SLA, and inactive accounts may be deleted.
- Some limits can be raised by identity verification via LinkedIn, which does not remove all limits.
- Serverless: Scala and R are not supported in notebooks; DataFrame and SQL cache APIs are not supported; Spark logs are not available for serverless notebooks and jobs.
- Git folders support HTTPS only. One older Databricks page lists dashboards as an unsupported asset type in Git folders; the current status is unverified.

Sources:
- <https://learn.microsoft.com/en-us/azure/databricks/getting-started/free-edition-limitations>
- <https://docs.databricks.com/aws/en/compute/serverless/limitations>
- <https://docs.databricks.com/aws/en/repos/limits>
