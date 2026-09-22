# Synthetic KPI definitions and verification

All values describe the generator, not a pharmaceutical market. SQL outputs
are produced by `run.py`; independent Pandas aggregates in `reconciliation.py`
must match before the run writes a PASS result in `outputs/reconciliation.json`.

| Metric | Definition and interpretation |
|---|---|
| Revenue | Sum of illustrative `revenue_usd`; no refunds, rebates or net-sales accounting |
| Prescriptions | Sum of synthetic monthly counts; rows are not individual orders |
| Active physicians | Count with prescriptions > 0 within each territory-month; do not sum months to obtain annual unique physicians |
| Monthly growth | 100 * (current Rx - previous Rx) / previous Rx, within territory; NULL for the first month or zero prior Rx |
| Revenue rank | Annual revenue rounded to cents, descending RANK; equal values share a rank and subsequent ranks can skip |
| Bottom revenue rank | Same calculation ascending; separate from target attainment |
| Top/bottom territories | Rank <= 3 in the corresponding direction; ties can include more than three territories |
| Contribution | 100 * territory revenue / all-territory revenue; NULL when total revenue is zero; rounded shares need not sum to exactly 100 |
| Target attainment | 100 * total Rx / total synthetic target; targets are illustrative |
| Response rate | 100 * recorded responses / contacts; a contact is a physician-month record, not a distinct annual physician |
| Cost per response | Total contact cost / responses; NULL when there are no responses; not ROI |
| Exposure-group activity | Rx per physician-month, grouped by month and whether outreach was recorded; no contact means response is unobserved |

Join `outreach` to prescription facts on **both** physician ID and month.
Joining on physician alone multiplies monthly observations and inflates totals.
The pipeline's unique-grain checks are a prerequisite for this join.

Contact selection depends on underlying simulated activity. Same-month data
has no within-month time ordering. Differences between exposure groups cannot
identify campaign effects. Segment comparisons use the full year and are
retrospective; they do not establish prospective targeting performance.

## Checkpoint commands (PowerShell, from the project directory)

```powershell
.\.venv-p1\Scripts\python.exe run.py
.\.venv-p1\Scripts\python.exe -m pytest -q
Get-Content outputs/reconciliation.json
Import-Csv outputs/territory_extremes.csv | Format-Table
Import-Csv outputs/exposure_comparison.csv | Select-Object -First 4 | Format-Table
```

Expect four reconciliation groups marked PASS for SQLite. New output files are
`territory_ranking.csv`, `territory_extremes.csv`, and `exposure_comparison.csv`.
Tests also exercise all-zero revenue, tied ranks, zero prior-month Rx, zero
responses, and deliberate output corruption. Float comparisons use absolute
tolerance 0.010001 and zero relative tolerance to accommodate rounding to cents
or hundredths of a percentage point; missing results must match.

MySQL equivalents are in `sql/05_mysql_comparisons.sql`. They are supplied for
future execution and are not covered by the SQLite reconciliation result.
Product analysis remains blocked by the absence of a product entity.

## Interview check

Explain why a physician-only join inflates counts, why missing outreach is not
a failed response, why rates must be recomputed from totals instead of averaged,
and why the top revenue territory can differ from the top target-attainment
territory. Use the generated CSVs to demonstrate each relevant definition.
