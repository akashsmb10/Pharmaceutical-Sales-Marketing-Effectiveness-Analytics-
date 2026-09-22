# MySQL 8 runbook — synthetic data only

These scripts are supplied but **not executed or verified** in this workspace. The `mysql` client was not found on PATH; server availability has not been established. Do not claim MySQL execution until the checks below succeed.

Prerequisites: MySQL 8.0.16+, a permitted account, `local_infile` enabled, and CSVs regenerated with `python run.py`.

Make a local copy of `sql/02_load_synthetic_csv.sql`, replace `C:/REPLACE_WITH_PROJECT_PATH` with the absolute repository path using forward slashes, then run:

```powershell
mysql --local-infile=1 -u root -p
```

Then inside the MySQL client, started from the repository directory:

```sql
SOURCE sql/01_mysql_schema.sql;
-- Substitute the filename of your edited local loader copy below.
SOURCE sql/02_load_synthetic_csv.local.sql;
SOURCE sql/03_data_quality_audit.sql;
SOURCE sql/04_mysql_analytics_views.sql;
SOURCE sql/05_mysql_comparisons.sql;
```

The schema script is for first-time setup. The loader **truncates all five
tables** in `pharma_sales_marketing_synthetic`; use only a dedicated disposable
synthetic database. It is not an atomic loader and still needs execution review,
including CSV line endings and load warnings. Stop on errors or warnings;
existing primary keys cannot prove that a loader did not skip duplicate rows.

All audit queries before `row_counts` should return zero rows. For seed 360, expected counts are 8 territories, 1,200 physicians, 3 campaigns, 14,400 physician-months, and 4,775 contacts. Compare totals to `outputs/validation.json`; the existing reconciliation applies to SQLite only.

Campaign views summarize non-randomly selected simulated contacts. They are not causal impact, incremental revenue, or ROI estimates.
