"""Generate synthetic data, validate a SQLite model, and export reports/dashboard."""
from pathlib import Path
import json
import sqlite3
import hashlib
import platform
import numpy as np
import pandas as pd
import plotly
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent
SEED = 360
VIEWS = ['monthly_performance', 'territory_performance', 'physician_segments',
         'campaign_performance', 'campaign_segment_response']


def generate(seed=SEED, n=1200):
    rng = np.random.default_rng(seed)
    territory = pd.DataFrame({'territory_id': range(1,9),
                              'territory_name': [f'Territory {i}' for i in range(1,9)]})
    physician = pd.DataFrame({'physician_id': np.arange(1,n+1),
                             'territory_id': rng.integers(1,9,n),
                             'specialty': rng.choice(['Primary care','Endocrinology','Internal medicine'],n)})
    base = rng.gamma(2.5,12,n)
    campaign = pd.DataFrame({'campaign_id':[1,2,3],
        'campaign_name':['Educational email','Webinar invitation','Field visit'],
        'channel':['Email','Webinar','Field']})
    facts, contacts = [], []
    for m in range(1,13):
        month=f'2025-{m:02d}'
        season=1+0.12*np.sin(2*np.pi*m/12)
        active=rng.random(n)>0.12
        volume=rng.poisson(base*season*(0.85+physician.territory_id.to_numpy()*0.04))*active
        price=rng.uniform(85,115,n)  # purely illustrative USD value per prescription
        facts.append(pd.DataFrame({'physician_id':physician.physician_id,'month':month,
            'prescriptions':volume,'revenue_usd':np.round(volume*price,2),
            'target_rx':np.maximum(1,np.rint(base*1.12)).astype(int)}))
        # Nonrandom contact selection is deliberately confounded by underlying activity.
        selected=np.flatnonzero(rng.random(n)<np.clip(0.15+base/170,0.15,0.8))
        channels=rng.integers(1,4,len(selected))
        response_p=np.clip(0.10+base[selected]/300+0.025*channels,0.05,0.7)
        contacts.append(pd.DataFrame({'physician_id':selected+1,'month':month,
            'campaign_id':channels,'responded':rng.binomial(1,response_p),
            'cost_usd':np.choose(channels-1,[2.0,18.0,75.0])}))
    return {'territory':territory,'physician':physician,'campaign':campaign,
            'prescription_month':pd.concat(facts,ignore_index=True),
            'outreach':pd.concat(contacts,ignore_index=True)}


def validate_frames(tables):
    p,f,o=tables['physician'],tables['prescription_month'],tables['outreach']
    assert p.physician_id.is_unique, 'Duplicate physician'
    assert not f.duplicated(['physician_id','month']).any(), 'Duplicate physician-month'
    assert not o.duplicated(['physician_id','month']).any(), 'Duplicate outreach grain'
    assert all(not t.isna().any().any() for t in tables.values()), 'Missing values'
    assert set(p.territory_id)<=set(tables['territory'].territory_id), 'Unknown territory'
    assert set(f.physician_id)<=set(p.physician_id), 'Orphan prescription'
    assert set(o.physician_id)<=set(p.physician_id), 'Orphan outreach'
    assert set(o.campaign_id)<=set(tables['campaign'].campaign_id), 'Unknown campaign'
    assert (f[['prescriptions','revenue_usd','target_rx']]>=0).all().all(), 'Negative value'
    assert (f.target_rx>0).all()
    assert o.responded.isin([0,1]).all(), 'Invalid response'
    assert f.groupby('physician_id').size().eq(12).all(), 'Missing observation months'
    return {'physicians':len(p),'physician_months':len(f),'contacts':len(o),
            'checks':'PASS: unique grains, required values, foreign keys, ranges, 12-month coverage'}


def build_database(tables, path):
    con=sqlite3.connect(path)
    for view in VIEWS:
        con.execute(f'DROP VIEW IF EXISTS {view}')
    for name,frame in tables.items():
        frame.to_sql(name,con,index=False,if_exists='replace')
    con.executescript('''
    CREATE UNIQUE INDEX IF NOT EXISTS physician_pk ON physician(physician_id);
    CREATE UNIQUE INDEX IF NOT EXISTS prescription_grain ON prescription_month(physician_id,month);
    CREATE UNIQUE INDEX IF NOT EXISTS outreach_grain ON outreach(physician_id,month);
    ''')
    con.executescript((ROOT/'sql/reports.sql').read_text())
    reports={v:pd.read_sql_query(f'SELECT * FROM {v}',con) for v in VIEWS}
    assert len(reports['physician_segments'])==len(tables['physician'])
    assert reports['territory_performance'].prescriptions.sum()==tables['prescription_month'].prescriptions.sum()
    assert np.isclose(reports['territory_performance'].revenue_usd.sum(),tables['prescription_month'].revenue_usd.sum())
    assert reports['campaign_performance'].contacts.sum()==len(tables['outreach'])
    con.close()
    return reports


def dashboard(reports,output):
    monthly=reports['monthly_performance']
    fig=make_subplots(rows=1,cols=2,subplot_titles=['Monthly prescriptions','Synthetic revenue (USD)'])
    groups=['All territories']+sorted(monthly.territory_name.unique().tolist())
    for i,name in enumerate(groups):
        df=monthly if i==0 else monthly[monthly.territory_name==name]
        agg=df.groupby('month')[['prescriptions','revenue_usd']].sum().reset_index()
        for j,col in enumerate(['prescriptions','revenue_usd']):
            fig.add_trace(go.Scatter(x=agg.month,y=agg[col],mode='lines+markers',
                name=name,visible=i==0,showlegend=False),row=1,col=j+1)
    buttons=[dict(label=name,method='update',args=[{'visible':[j//2==i for j in range(2*len(groups))]}])
             for i,name in enumerate(groups)]
    fig.update_layout(template='plotly_white',height=400,
        updatemenus=[dict(buttons=buttons,x=0,y=1.25)],margin=dict(t=100))
    territory=px.bar(reports['territory_performance'],x='territory_name',y='target_attainment_pct',
        title='Prescription target attainment (synthetic targets)',template='plotly_white')
    segments=reports['physician_segments'].segment.value_counts().rename_axis('segment').reset_index(name='physicians')
    segment=px.bar(segments,x='segment',y='physicians',title='Descriptive physician activity segments',template='plotly_white')
    campaign=px.bar(reports['campaign_performance'],x='channel',y='response_rate_pct',
        title='Observed response among contacts — not causal uplift',template='plotly_white')
    blocks=[f.to_html(full_html=False,include_plotlyjs=True if i==0 else False)
            for i,f in enumerate([fig,territory,segment,campaign])]
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Pharmaceutical Commercial Analytics</title><style>body{font:16px system-ui;margin:32px auto;max-width:1150px;padding:0 20px;color:#172b4d} .note{background:#eef4fb;padding:18px;border-radius:8px}</style>
    <h1>Pharmaceutical Commercial Analytics</h1><p class="note">Independent portfolio study. All data and financial values are synthetic. Campaign response is descriptive; no causal sales impact or ROI is estimated. Use the territory dropdown to explore trends.</p>'''
    (output/'dashboard.html').write_text(html+''.join(blocks)+'</html>',encoding='utf-8')


def main():
    data,output=ROOT/'data',ROOT/'outputs'
    data.mkdir(exist_ok=True); output.mkdir(exist_ok=True)
    tables=generate(); audit=validate_frames(tables)
    hashes={}
    for name,frame in tables.items():
        path=data/f'{name}.csv'; frame.to_csv(path,index=False)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    reports=build_database(tables,output/'analytics.sqlite')
    for name,frame in reports.items(): frame.to_csv(output/f'{name}.csv',index=False)
    dashboard(reports,output)
    audit.update({'seed':SEED,'data_type':'synthetic','source_sha256':hashes,
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'plotly':plotly.__version__},
        'prescriptions':int(tables['prescription_month'].prescriptions.sum()),
        'responses':int(tables['outreach'].responded.sum()),'sql_reconciliation':'PASS'})
    (output/'validation.json').write_text(json.dumps(audit,indent=2))
    t=reports['territory_performance'].sort_values('target_attainment_pct')
    c=reports['campaign_performance'].sort_values('cost_per_response_usd')
    report=f'''# Commercial findings — synthetic demonstration

Generated {audit['physicians']:,} physicians, {audit['physician_months']:,} physician-months and {audit['contacts']:,} campaign contacts with seed {SEED}.

## Observations
- Prescription volume totals {audit['prescriptions']:,}; SQL totals reconcile to the source facts.
- {t.iloc[0].territory_name} has the lowest synthetic target attainment ({t.iloc[0].target_attainment_pct:.2f}%). Review its activity mix and target assumptions before proposing a resource change.
- {t.iloc[-1].territory_name} has the highest synthetic target attainment ({t.iloc[-1].target_attainment_pct:.2f}%). This is a descriptive comparison, not evidence of representative effectiveness.
- {c.iloc[0].channel} has the lowest observed synthetic cost per response (${c.iloc[0].cost_per_response_usd:.2f}). Channel populations differ; this does not establish an optimal channel or incremental revenue.

## Recommended next decisions
1. Validate commercial definitions and target comparability with stakeholders before using this design on real data.
2. Review physician activity segments by territory to form hypotheses about coverage, without using them as clinical prescribing recommendations.
3. For causal campaign evaluation, pre-specify a randomized, appropriately powered pilot with a holdout and incremental outcome definition; these reports alone cannot support an uplift claim.

## Limits
The generator sets activity, seasonality and response probabilities. Findings describe that simulation, not a pharmaceutical market. Segments use the full year and are retrospective. The dashboard is Plotly HTML; a Power BI import guide is supplied, but no PBIX report has been built.
'''
    (output/'findings.md').write_text(report,encoding='utf-8')
    print(json.dumps(audit,indent=2))


if __name__=='__main__': main()
