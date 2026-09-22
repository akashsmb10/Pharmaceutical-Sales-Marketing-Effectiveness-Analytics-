import sqlite3
import numpy as np
import pytest
from run import generate, validate_frames, build_database


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
