# Power BI build guide

All source files are synthetic. Run `python run.py` first, then import the CSVs from `outputs/` into Power BI Desktop.

1. Load `monthly_performance.csv`, `territory_performance.csv`, `product_performance.csv`, `physician_segments.csv`, `campaign_performance.csv`, `campaign_segment_response.csv`, and `exposure_comparison.csv`.
2. Format `revenue_usd` and `contact_cost_usd` as currency. Import `data/calendar.csv` if a date table is required.
3. Add KPI cards for revenue, prescriptions, active physicians, and latest-month growth. Do not sum percentage rows.
4. Add charts for monthly trend, territory target attainment, product revenue, physician segments, campaign response rate, and exposure-group activity.
5. Add date, territory, product, and segment slicers where the imported table supports the field. For a fully relational model, import the source CSVs in `data/` and recreate the SQL logic.
6. Add this disclaimer: “Synthetic/simulated data. Campaign comparisons are descriptive only and do not estimate causal impact or ROI.”

“No contact recorded” means response is unobserved; it does not mean a failed response. Same-month exposure comparisons do not establish campaign effectiveness.
