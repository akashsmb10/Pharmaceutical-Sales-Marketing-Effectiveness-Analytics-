# Pharmaceutical Sales & Marketing Effectiveness Analytics

> **Synthetic/simulated portfolio project.** No real patient, physician, client, pharmaceutical-company, prescription, sales, or campaign data is included. Every record and result is generated locally for learning.

## Business question

This project shows how a fictional commercial team can describe prescription activity, illustrative revenue, product and territory performance, physician activity segments, and observed campaign responses.

It supports descriptive analysis only. It does not estimate campaign uplift, causal impact, ROI, clinical outcomes, or real-world market performance.

## Dataset and model

`run.py` generates seven deterministic CSV tables with NumPy seed `360`: territory, physician, product, calendar, campaign, physician-product-month prescription facts, and physician-month outreach facts. No external data is downloaded, so no third-party dataset license applies. The generator's product shares, prices, targeting, contact selection, and response probabilities are assumptions, not observed behavior.

```text
territory (1) --< physician (1) --< prescription_month >-- (1) product
                                            |
                                          (1) calendar
physician (1) --< outreach >-- (1) campaign
```

`prescription_month` is at physician-product-month grain. `outreach` is at physician-month grain; any campaign comparison aggregates prescriptions to physician-month before joining. See [the data dictionary](docs/data_dictionary.md).

## KPIs and analysis

- Monthly prescriptions, illustrative revenue, active physicians, and growth.
- Territory and product revenue, contribution, target attainment, and rankings.
- Retrospective physician activity segments.
- Campaign contact, response rate, and cost per response.
- Same-month activity by recorded campaign exposure, labelled descriptive only.

The SQLite workflow creates CSV extracts, `analytics.sqlite`, a dashboard, six standalone HTML charts, findings, and source-versus-SQL reconciliation. [KPI definitions](docs/kpi_definitions.md) document denominators and interpretation.

## Run on Windows

```powershell
cd pharmaceutical-sales-marketing-analytics
.\.venv-p1\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
python -m pytest -q
```

Successful execution writes `outputs/validation.json` with `data_type: synthetic` and `sql_reconciliation: PASS`, and `outputs/reconciliation.json` with status `PASS`.

## Dashboard and Power BI

Open `outputs/dashboard.html` or any file in `outputs/charts/` after running the pipeline. To build a local Power BI report from generated outputs, use [the Power BI build guide](dashboard/powerbi_build_guide.md). No PBIX or dashboard screenshots are committed.

## Findings and limitations

Generated findings are in `outputs/findings.md`. They describe the simulation only. Contacts are selected non-randomly, and same-month activity has no time ordering; campaign comparisons cannot show causal effectiveness. Segments use the full year and are retrospective. Territory labels, products, prices, targets, and revenue are placeholders. Product-level results depend on generator assumptions.

## SQL

The runnable workflow executes SQLite views in `sql/reports.sql`. MySQL 8 schema, loading, quality-audit, and analytical scripts are in `sql/`; they are provided for use with a local server but have not been executed in this workspace. See [the MySQL runbook](docs/mysql_runbook.md).
