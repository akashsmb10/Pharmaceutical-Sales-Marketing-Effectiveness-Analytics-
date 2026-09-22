# MySQL 8 runbook — synthetic data only

These scripts are supplied but **not executed or verified** in this workspace: no MySQL client/server is installed here. Do not claim MySQL execution until the checks below succeed.

Prerequisites: MySQL 8.0.16+, a permitted account, `local_infile` enabled, and CSVs regenerated with `python run.py`.

Make a local copy of `sql/02_load_synthetic_csv.sql`, replace `C:/REPLACE_WITH_PROJECT_PATH` with the absolute repository path using forward slashes, then run:

```powershell
mysql --local-infile=1 -u root -p < sql/01_mysql_schema.sql
mysql --local-infile=1 -u root -p < sql/02_load_synthetic_csv.sql
mysql --local-infile=1 -u root -p < sql/03_data_quality_audit.sql
mysql --local-infile=1 -u root -p < sql/04_mysql_analytics_views.sql
```

All audit queries before `row_counts` should return zero rows. For seed 360, expected counts are 8 territories, 1,200 physicians, 3 campaigns, 14,400 physician-months, and 4,775 contacts. Compare totals to `outputs/validation.json`; the existing reconciliation applies to SQLite only.

Campaign views summarize non-randomly selected simulated contacts. They are not causal impact, incremental revenue, or ROI estimates.
