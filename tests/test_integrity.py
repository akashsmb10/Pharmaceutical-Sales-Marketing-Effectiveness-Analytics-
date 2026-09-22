import sqlite3
import numpy as np
import pytest
from run import generate, validate_frames, build_database
from reconciliation import reconcile


def test_independent_pandas_reconciliation(tmp_path):
    tables = generate(n=80)
    reports = build_database(tables, tmp_path/'reconcile.sqlite')
    assert reconcile(tables, reports)['status'] == 'PASS'
    # Prove the checker detects a material error, not only a successful run.
    reports['monthly_performance'].loc[0, 'revenue_usd'] += 1
    with pytest.raises(AssertionError):
        reconcile(tables, reports)


def test_zero_denominators_and_tied_ranks(tmp_path):
    tables = generate(n=80)
    tables['prescription_month']['revenue_usd'] = 0.0
    tables['prescription_month'].loc[
        tables['prescription_month'].month == '2025-01', 'prescriptions'] = 0
    tables['outreach']['responded'] = 0
    reports = build_database(tables, tmp_path/'edge.sqlite')
    reconcile(tables, reports)
    ranked = reports['territory_ranking']
    assert ranked.revenue_rank.eq(1).all()
    assert ranked.revenue_contribution_pct.isna().all()
    assert len(reports['territory_extremes']) == 2*len(ranked)
    monthly = reports['monthly_performance']
    assert monthly.loc[monthly.month == '2025-02', 'rx_growth_pct'].isna().all()
    assert reports['campaign_performance'].cost_per_response_usd.isna().all()
    exposure = reports['exposure_comparison']
    assert exposure.physician_months.sum() == len(tables['physician']) * len(tables['calendar'])
    assert exposure.loc[exposure.exposure_group == 'No contact recorded', 'responses'].isna().all()


def test_reconciled_reports_and_denominators(tmp_path):
    tables=generate(n=80)
    validate_frames(tables)
    reports=build_database(tables,tmp_path/'test.sqlite')
    monthly=reports['monthly_performance']
    assert monthly[monthly.month=='2025-01'].rx_growth_pct.isna().all()
    assert set(reports['physician_segments'].physician_id)==set(tables['physician'].physician_id)
    for row in reports['campaign_performance'].itertuples():
        assert np.isclose(row.response_rate_pct,round(100*row.responses/row.contacts,2))
    assert reports['campaign_performance'].responses.sum()==tables['outreach'].responded.sum()


@pytest.mark.parametrize('damage',['duplicate','orphan','negative'])
def test_invalid_source_rejected(damage):
    tables=generate(n=30)
    frame=tables['prescription_month']
    if damage=='duplicate': frame.loc[1]=frame.loc[0]
    elif damage=='orphan': frame.loc[0,'physician_id']=99999
    else: frame.loc[0,'prescriptions']=-1
    with pytest.raises(AssertionError): validate_frames(tables)


def test_reproducible_generation():
    a,b=generate(n=20),generate(n=20)
    assert all(a[k].equals(b[k]) for k in a)
