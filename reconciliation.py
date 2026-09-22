"""Independent source-frame calculations for synthetic SQLite report checks."""
import numpy as np
import pandas as pd


def reconcile(tables, reports):
    checks = []

    def compare(name, actual, expected, keys, columns):
        actual = actual.set_index(keys).sort_index()
        expected = expected.set_index(keys).sort_index()
        pd.testing.assert_index_equal(actual.index, expected.index)
        for column in columns:
            # SQL and Pandas may round decimal ties differently. Allow one cent
            # or 0.01 percentage point, with no relative tolerance.
            np.testing.assert_allclose(actual[column].to_numpy(dtype=float),
                                       expected[column].to_numpy(dtype=float),
                                       atol=0.010001, rtol=0, equal_nan=True,
                                       err_msg=f'{name}: {column}')
        checks.append(name)

    facts = tables['prescription_month'].merge(
        tables['physician'][['physician_id','territory_id']],
        on='physician_id', validate='many_to_one')
    facts['active'] = (facts.prescriptions > 0).astype(int)
    monthly = facts.groupby(['territory_id','month'], as_index=False).agg(
        prescriptions=('prescriptions','sum'), revenue_usd=('revenue_usd','sum'),
        active_physicians=('active','sum'))
    previous = monthly.groupby('territory_id').prescriptions.shift()
    monthly['rx_growth_pct'] = 100 * (monthly.prescriptions-previous)/previous.replace(0,np.nan)
    compare('monthly totals, active physicians and growth', reports['monthly_performance'],
            monthly, ['territory_id','month'],
            ['prescriptions','revenue_usd','active_physicians','rx_growth_pct'])

    territory = facts.groupby('territory_id', as_index=False).agg(
        revenue_usd=('revenue_usd','sum'))
    territory.revenue_usd = territory.revenue_usd.round(2)
    territory['revenue_rank'] = territory.revenue_usd.rank(method='min',ascending=False)
    territory['bottom_revenue_rank'] = territory.revenue_usd.rank(method='min')
    territory['revenue_contribution_pct'] = 100*territory.revenue_usd/territory.revenue_usd.sum()
    compare('territory revenue ranks and contribution',reports['territory_ranking'],territory,
            ['territory_id'],['revenue_usd','revenue_rank','bottom_revenue_rank','revenue_contribution_pct'])

    outreach = tables['outreach']
    campaign = outreach.groupby('campaign_id', as_index=False).agg(
        contacts=('physician_id','size'), responses=('responded','sum'),
        contact_cost_usd=('cost_usd','sum'))
    campaign['response_rate_pct'] = 100*campaign.responses/campaign.contacts
    campaign['cost_per_response_usd'] = campaign.contact_cost_usd/campaign.responses.replace(0,np.nan)
    compare('campaign response denominators and costs',reports['campaign_performance'],campaign,
            ['campaign_id'],['contacts','responses','contact_cost_usd','response_rate_pct','cost_per_response_usd'])

    exposed = facts.merge(outreach,on=['physician_id','month'],how='left',
                          validate='one_to_one',indicator=True)
    exposed['exposure_group'] = np.where(exposed['_merge']=='both',
                                         'Contact recorded','No contact recorded')
    comparison = exposed.groupby(['month','exposure_group'],as_index=False).agg(
        physician_months=('physician_id','size'), prescriptions=('prescriptions','sum'),
        revenue_usd=('revenue_usd','sum'), rx_per_physician_month=('prescriptions','mean'),
        contacts=('responded','count'), responses=('responded',lambda x:x.sum(min_count=1)))
    comparison['response_rate_pct'] = 100*comparison.responses/comparison.contacts.replace(0,np.nan)
    compare('exposure groups, activity and missing responses',reports['exposure_comparison'],comparison,
            ['month','exposure_group'],['physician_months','prescriptions','revenue_usd',
            'rx_per_physician_month','contacts','responses','response_rate_pct'])
    return {'data_type':'synthetic','engine':'SQLite','status':'PASS','checks':checks}
