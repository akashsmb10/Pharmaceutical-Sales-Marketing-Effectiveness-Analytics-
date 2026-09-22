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
from reconciliation import reconcile

ROOT = Path(__file__).resolve().parent
SEED = 360
VIEWS = ['monthly_performance', 'territory_performance', 'physician_segments',
         'campaign_performance', 'campaign_segment_response',
         'territory_ranking', 'territory_extremes', 'exposure_comparison',
         'product_performance']


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
    product = pd.DataFrame({
        'product_id':[1,2,3],
        'product_name':['Product A','Product B','Product C'],
        'therapy_area':['Metabolic','Metabolic','Cardiovascular'],
        'base_price_usd':[92.0,108.0,126.0]
    })
    calendar = pd.DataFrame({'month':[f'2025-{m:02d}' for m in range(1,13)]})
    calendar['month_start'] = calendar.month + '-01'
    calendar['quarter'] = ['Q1','Q1','Q1','Q2','Q2','Q2','Q3','Q3','Q3','Q4','Q4','Q4']
    calendar['year'] = 2025
    facts, contacts = [], []
    for m in range(1,13):
        month=f'2025-{m:02d}'
        season=1+0.12*np.sin(2*np.pi*m/12)
        active=rng.random(n)>0.12
        volume=rng.poisson(base*season*(0.85+physician.territory_id.to_numpy()*0.04))*active
        # Allocate each physician-month total across three simulated products.
        # Shares are fixed generator assumptions, not observed market shares.
        allocations=np.array([rng.multinomial(v,[0.46,0.34,0.20]) for v in volume])
        target_total=np.maximum(1,np.rint(base*1.12)).astype(int)
        target_allocations=np.array([rng.multinomial(v,[0.46,0.34,0.20]) for v in target_total])
        for i, item in product.iterrows():
            price=rng.uniform(item.base_price_usd*.92,item.base_price_usd*1.08,n)
            rx=allocations[:,i]
            facts.append(pd.DataFrame({'physician_id':physician.physician_id,
                'product_id':item.product_id,'month':month,'prescriptions':rx,
                'revenue_usd':np.round(rx*price,2),'target_rx':target_allocations[:,i]}))
        # Nonrandom contact selection is deliberately confounded by underlying activity.
        selected=np.flatnonzero(rng.random(n)<np.clip(0.15+base/170,0.15,0.8))
        channels=rng.integers(1,4,len(selected))
        response_p=np.clip(0.10+base[selected]/300+0.025*channels,0.05,0.7)
        contacts.append(pd.DataFrame({'physician_id':selected+1,'month':month,
            'campaign_id':channels,'responded':rng.binomial(1,response_p),
            'cost_usd':np.choose(channels-1,[2.0,18.0,75.0])}))
    return {'territory':territory,'physician':physician,'campaign':campaign,
            'product':product,'calendar':calendar,
            'prescription_month':pd.concat(facts,ignore_index=True),
            'outreach':pd.concat(contacts,ignore_index=True)}


def validate_frames(tables):
    p,f,o=tables['physician'],tables['prescription_month'],tables['outreach']
    assert p.physician_id.is_unique, 'Duplicate physician'
    assert not f.duplicated(['physician_id','product_id','month']).any(), 'Duplicate physician-product-month'
    assert not o.duplicated(['physician_id','month']).any(), 'Duplicate outreach grain'
    assert all(not t.isna().any().any() for t in tables.values()), 'Missing values'
    assert set(p.territory_id)<=set(tables['territory'].territory_id), 'Unknown territory'
    assert set(f.physician_id)<=set(p.physician_id), 'Orphan prescription'
    assert set(f.product_id)<=set(tables['product'].product_id), 'Unknown product'
    assert set(f.month)<=set(tables['calendar'].month), 'Unknown calendar month'
    assert set(o.physician_id)<=set(p.physician_id), 'Orphan outreach'
    assert set(o.campaign_id)<=set(tables['campaign'].campaign_id), 'Unknown campaign'
    assert (f[['prescriptions','revenue_usd','target_rx']]>=0).all().all(), 'Negative value'
    assert (f.target_rx>=0).all()
    assert o.responded.isin([0,1]).all(), 'Invalid response'
    assert f.groupby('physician_id').month.nunique().eq(12).all(), 'Missing observation months'
    assert f.groupby(['physician_id','month']).product_id.nunique().eq(len(tables['product'])).all(), 'Missing product coverage'
    return {'physicians':len(p),'prescription_rows':len(f),'contacts':len(o),
            'checks':'PASS: unique grains, required values, foreign keys, ranges, calendar and product coverage'}


def build_database(tables, path):
    con=sqlite3.connect(path)
    for view in reversed(VIEWS):
        con.execute(f'DROP VIEW IF EXISTS {view}')
    for name,frame in tables.items():
        frame.to_sql(name,con,index=False,if_exists='replace')
    con.executescript('''
    CREATE UNIQUE INDEX IF NOT EXISTS physician_pk ON physician(physician_id);
    CREATE UNIQUE INDEX IF NOT EXISTS product_pk ON product(product_id);
    CREATE UNIQUE INDEX IF NOT EXISTS calendar_pk ON calendar(month);
    CREATE UNIQUE INDEX IF NOT EXISTS prescription_grain ON prescription_month(physician_id,product_id,month);
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
    charts=output/'charts'
    charts.mkdir(exist_ok=True)
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
    palette=['#2563eb','#0f766e','#7c3aed','#ea580c','#db2777','#0891b2','#65a30d','#64748b','#dc2626']
    fig.update_layout(template='plotly_white',height=360,
        paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='white',font=dict(color='#172554'),
        updatemenus=[dict(buttons=buttons,x=0,y=1.25)],margin=dict(t=100))
    territory=px.bar(reports['territory_performance'].sort_values('target_attainment_pct'),x='territory_name',y='target_attainment_pct',
        title='Prescription target attainment (synthetic targets)',template='plotly_white')
    segments=reports['physician_segments'].segment.value_counts().rename_axis('segment').reset_index(name='physicians')
    segment=px.bar(segments,x='segment',y='physicians',title='Descriptive physician activity segments',template='plotly_white')
    campaign=px.bar(reports['campaign_performance'],x='channel',y='response_rate_pct',
        title='Observed response among contacts — not causal uplift',template='plotly_white')
    product=px.bar(reports['product_performance'].sort_values('revenue_usd',ascending=False),
        x='product_name',y='revenue_usd',color='therapy_area',
        title='Synthetic revenue by product',template='plotly_white')
    exposure=px.line(reports['exposure_comparison'],x='month',y='rx_per_physician_month',
        color='exposure_group',markers=True,
        title='Same-month activity by recorded campaign exposure',template='plotly_white')
    figures=[fig,territory,segment,campaign,product,exposure]
    for figure in figures:
        figure.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='white',font=dict(color='#172554'),
                             margin=dict(l=42,r=20,t=62,b=42),colorway=palette)
        figure.update_xaxes(showgrid=False)
        figure.update_yaxes(gridcolor='#e2e8f0',zeroline=False)
    for name,figure in {'monthly_trends':fig,'territory_performance':territory,
                         'physician_segments':segment,'campaign_response':campaign,
                         'product_performance':product,'exposure_comparison':exposure}.items():
        figure.write_html(charts/f'{name}.html',include_plotlyjs='cdn')
    blocks=[f'<section class="panel {"wide" if i == 0 else ""}">{f.to_html(full_html=False,include_plotlyjs=True if i==0 else False)}</section>'
            for i,f in enumerate(figures)]
    monthly_all=monthly.groupby('month',as_index=False).agg(revenue_usd=('revenue_usd','sum'),prescriptions=('prescriptions','sum'),active_physicians=('active_physicians','sum'))
    total_revenue=monthly_all.revenue_usd.sum(); total_rx=monthly_all.prescriptions.sum()
    latest_growth=(monthly_all.prescriptions.iloc[-1]/monthly_all.prescriptions.iloc[-2]-1)*100
    best_channel=reports['campaign_performance'].sort_values('cost_per_response_usd').iloc[0]
    cards=f'''<div class="cards">
    <article><span>Illustrative revenue</span><strong>${total_revenue/1e6:.1f}M</strong><small>Synthetic 2025 portfolio</small></article>
    <article><span>Prescriptions</span><strong>{total_rx/1000:.0f}K</strong><small>Across all territories</small></article>
    <article><span>Latest-month growth</span><strong>{latest_growth:+.1f}%</strong><small>Prescription volume MoM</small></article>
    <article><span>Lowest cost / response</span><strong>{best_channel.channel}</strong><small>${best_channel.cost_per_response_usd:.0f} per recorded response</small></article></div>'''
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Pharmaceutical Commercial Analytics</title><style>
    *{box-sizing:border-box} body{margin:0;background:#f5f8fc;color:#172554;font:15px Inter,system-ui,-apple-system,sans-serif} .shell{max-width:1440px;margin:auto;padding:36px 28px 56px}.hero{background:linear-gradient(120deg,#0f2b5b,#2563eb);color:white;border-radius:20px;padding:32px 34px;margin-bottom:22px;box-shadow:0 12px 30px #1e3a8a33}.eyebrow{text-transform:uppercase;letter-spacing:.11em;font-weight:700;font-size:11px;opacity:.78}.hero h1{font-size:32px;margin:8px 0}.hero p{max-width:780px;line-height:1.55;margin:0;color:#dbeafe}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}.cards article,.panel{background:#fff;border:1px solid #e5edf8;border-radius:16px;box-shadow:0 4px 14px #1e3a8a0c}.cards article{padding:19px}.cards span,.cards small{display:block;color:#64748b}.cards strong{display:block;font-size:27px;margin:8px 0;color:#172554}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.panel{overflow:hidden}.wide{grid-column:1/-1}.notice{margin-top:18px;padding:14px 17px;border-radius:12px;background:#fff7ed;color:#9a3412;border:1px solid #fed7aa;line-height:1.45}@media(max-width:850px){.cards,.grid{grid-template-columns:1fr}.wide{grid-column:auto}.shell{padding:18px}.hero{padding:25px}.hero h1{font-size:26px}}</style>
    <main class="shell"><header class="hero"><div class="eyebrow">Executive commercial dashboard · portfolio simulation</div><h1>Pharmaceutical Sales &amp; Marketing Effectiveness</h1><p>Explore synthetic commercial performance across revenue, territory execution, product mix, physician activity, and recorded campaign response.</p></header>'''
    disclaimer='<p class="notice"><strong>Interpret with care:</strong> all data and financial values are synthetic. Campaign response and exposure comparisons are descriptive only; they do not estimate causal impact, incremental sales, or ROI.</p></main>'
    (output/'dashboard.html').write_text(html+cards+'<div class="grid">'+''.join(blocks)+'</div>'+disclaimer+'</html>',encoding='utf-8')


def main():
    data,output=ROOT/'data',ROOT/'outputs'
    data.mkdir(exist_ok=True); output.mkdir(exist_ok=True)
    tables=generate(); audit=validate_frames(tables)
    hashes={}
    for name,frame in tables.items():
        path=data/f'{name}.csv'; frame.to_csv(path,index=False)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    reports=build_database(tables,output/'analytics.sqlite')
    reconciliation = reconcile(tables, reports)
    (output/'reconciliation.json').write_text(json.dumps(reconciliation,indent=2))
    for name,frame in reports.items(): frame.to_csv(output/f'{name}.csv',index=False)
    dashboard(reports,output)
    audit.update({'seed':SEED,'data_type':'synthetic','source_sha256':hashes,
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'plotly':plotly.__version__},
        'prescriptions':int(tables['prescription_month'].prescriptions.sum()),
        'responses':int(tables['outreach'].responded.sum()),'sql_reconciliation':'PASS',
        'reconciliation_engine':'SQLite','reconciled_metrics':reconciliation['checks']})
    (output/'validation.json').write_text(json.dumps(audit,indent=2))
    t=reports['territory_performance'].sort_values('target_attainment_pct')
    c=reports['campaign_performance'].sort_values('cost_per_response_usd')
    report=f'''# Commercial findings — synthetic demonstration

Generated {audit['physicians']:,} physicians, {audit['prescription_rows']:,} synthetic physician-product-month rows and {audit['contacts']:,} campaign contacts with seed {SEED}.

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
The generator sets activity, seasonality and response probabilities. Findings describe that simulation, not a pharmaceutical market. Segments use the full year and are retrospective. The dashboard is Plotly HTML; a Power BI import guide and PBIX report remain pending.
'''
    (output/'findings.md').write_text(report,encoding='utf-8')
    print(json.dumps(audit,indent=2))


if __name__=='__main__': main()
