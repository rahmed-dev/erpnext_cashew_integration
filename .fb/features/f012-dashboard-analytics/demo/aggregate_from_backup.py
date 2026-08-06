import sqlite3, json, datetime, collections, zoneinfo

DB = '/home/riz/work-bench/cashew-2026-07-04-18-03-44-147880.sql'
TZ = zoneinfo.ZoneInfo('Asia/Karachi')
USD_PKR = 278.0  # demo approximation; ERP uses per-row actual transacted rate

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

wallets = {r['wallet_pk']: dict(name=r['name'], ccy=r['currency'].upper())
           for r in c.execute('select wallet_pk,name,currency from wallets')}
cats = {r['category_pk']: dict(name=r['name'], income=r['income'])
        for r in c.execute('select category_pk,name,income from categories')}

rows = []
for r in c.execute('select * from transactions where paid=1'):
    w = wallets.get(r['wallet_fk'], dict(name='?', ccy='PKR'))
    cat = cats.get(r['category_fk'], dict(name='Uncategorized'))
    d = datetime.datetime.fromtimestamp(r['date_created'], TZ).date()
    amt = abs(r['amount'])
    base = amt * (USD_PKR if w['ccy'] == 'USD' else 1.0)
    rows.append(dict(date=d.isoformat(), month=d.strftime('%Y-%m'),
                     income=bool(r['income']), amt=amt, base=base,
                     wallet=w['name'], ccy=w['ccy'], cat=cat['name'],
                     paired=r['paired_transaction_fk'], note=r['note'] or ''))

TRANSFER = {'Balance Correction', 'Balance Transfer'}
ops = [r for r in rows if r['cat'] not in TRANSFER]
xfers = [r for r in rows if r['cat'] in TRANSFER]

# --- monthly income / expense / net
m = collections.defaultdict(lambda: [0.0, 0.0])
for r in ops:
    m[r['month']][0 if r['income'] else 1] += r['base']
months = sorted(m)
monthly = dict(months=months,
               income=[round(m[k][0]) for k in months],
               expense=[round(m[k][1]) for k in months],
               net=[round(m[k][0] - m[k][1]) for k in months])

# --- expense treemap by category
tm = collections.defaultdict(float)
for r in ops:
    if not r['income']:
        tm[r['cat']] += r['base']
treemap = sorted(({'name': k, 'value': round(v)} for k, v in tm.items()),
                 key=lambda x: -x['value'])

# --- income by category (for sankey left side)
inc = collections.defaultdict(float)
for r in ops:
    if r['income']:
        inc[r['cat']] += r['base']

# --- daily spend calendar
cal = collections.defaultdict(float)
for r in ops:
    if not r['income']:
        cal[r['date']] += r['base']
calendar = sorted([[k, round(v)] for k, v in cal.items()])

# --- per-wallet running balance over time (all rows incl. transfers)
by_day = collections.defaultdict(lambda: collections.defaultdict(float))
for r in rows:
    by_day[r['date']][r['wallet']] += (r['base'] if r['income'] else -r['base'])
days = sorted(by_day)
wnames = sorted({r['wallet'] for r in rows})
run = {w: 0.0 for w in wnames}
series = {w: [] for w in wnames}
networth = []
# sample monthly to keep the chart readable
seen_months = {}
for d in days:
    for w, v in by_day[d].items():
        run[w] += v
    seen_months[d[:7]] = dict(run)
bmonths = sorted(seen_months)
for w in wnames:
    series[w] = [round(seen_months[mm].get(w, 0)) for mm in bmonths]
networth = [round(sum(seen_months[mm].values())) for mm in bmonths]

# --- sankey: income cat -> wallet -> expense cat (top N each side)
TOPN = 6
top_inc = sorted(inc.items(), key=lambda x: -x[1])[:TOPN]
top_exp = sorted(tm.items(), key=lambda x: -x[1])[:TOPN]
inc_names = {k for k, _ in top_inc}
exp_names = {k for k, _ in top_exp}
links = collections.defaultdict(float)
for r in ops:
    if r['income'] and r['cat'] in inc_names:
        links[(r['cat'], r['wallet'])] += r['base']
    elif (not r['income']) and r['cat'] in exp_names:
        links[(r['wallet'], r['cat'])] += r['base']
nodes = sorted({n for pair in links for n in pair})
sankey = dict(nodes=[{'name': n} for n in nodes],
              links=[{'source': a, 'target': b, 'value': round(v)}
                     for (a, b), v in links.items() if v > 0])

# --- KPI
total_exp = sum(r['base'] for r in ops if not r['income'])
total_inc = sum(r['base'] for r in ops if r['income'])
# ERP routing mirror: income -> Sales Invoice, expense above threshold -> Purchase Invoice
PI_THRESHOLD = 5000.0
si = [r for r in ops if r['income']]
pi = [r for r in ops if not r['income'] and r['base'] >= PI_THRESHOLD]
je = [r for r in ops if not r['income'] and r['base'] < PI_THRESHOLD]


# --- per-month breakdowns so the demo's period filter can recompute client-side
cat_month = collections.defaultdict(lambda: collections.defaultdict(float))
inc_cat_month = collections.defaultdict(lambda: collections.defaultdict(float))
kpi_month = {}
link_month = collections.defaultdict(lambda: collections.defaultdict(float))
for r in ops:
    mm = r['month']
    if r['income']:
        inc_cat_month[mm][r['cat']] += r['base']
    else:
        cat_month[mm][r['cat']] += r['base']
    k = kpi_month.setdefault(mm, dict(inc=0.0, exp=0.0, si_c=0, si_v=0.0,
                                      pi_c=0, pi_v=0.0, je_c=0, je_v=0.0))
    if r['income']:
        k['inc'] += r['base']; k['si_c'] += 1; k['si_v'] += r['base']
    else:
        k['exp'] += r['base']
        if r['base'] >= PI_THRESHOLD:
            k['pi_c'] += 1; k['pi_v'] += r['base']
        else:
            k['je_c'] += 1; k['je_v'] += r['base']
    if r['income'] and r['cat'] in inc_names:
        link_month[mm][r['cat'] + '|' + r['wallet']] += r['base']
    elif (not r['income']) and r['cat'] in exp_names:
        link_month[mm][r['wallet'] + '|' + r['cat']] += r['base']

by_month = dict(
    expense_cats={m: {k: round(v) for k, v in d.items()} for m, d in cat_month.items()},
    income_cats={m: {k: round(v) for k, v in d.items()} for m, d in inc_cat_month.items()},
    links={m: {k: round(v) for k, v in d.items()} for m, d in link_month.items()},
    kpi={m: {k: round(v) for k, v in d.items()} for m, d in kpi_month.items()},
)

# --- budgets (Cashew's Goals + spending limits live here, NOT in objectives)
budgets = []
for b in c.execute('select * from budgets'):
    cfk = json.loads(b['category_fks']) if b['category_fks'] else []
    wfk = json.loads(b['wallet_fks']) if b['wallet_fks'] else []
    agg = collections.defaultdict(float)
    for t in c.execute('select amount,date_created,category_fk,wallet_fk,income from transactions where paid=1'):
        if cfk and t['category_fk'] not in cfk:
            continue
        if wfk and t['wallet_fk'] not in wfk:
            continue
        if bool(t['income']) != bool(b['income']):
            continue
        mm = datetime.datetime.fromtimestamp(t['date_created'], TZ).strftime('%Y-%m')
        agg[mm] += abs(t['amount'])
    ms = sorted(agg)
    budgets.append(dict(
        name=b['name'], amount=b['amount'], income=bool(b['income']),
        pinned=bool(b['pinned']), archived=bool(b['archived']),
        categories=[cats.get(x, {}).get('name', x) for x in cfk],
        wallets=[wallets.get(x, {}).get('name', x) for x in wfk] or
                [wallets.get(b['wallet_fk'], {}).get('name', '?')],
        months=ms, actuals=[round(agg[k]) for k in ms],
    ))

# --- goals
goals = [dict(r) for r in c.execute('select name,type,amount,end_date,archived,pinned,wallet_fk from objectives')]
for g in goals:
    g['wallet'] = wallets.get(g['wallet_fk'], {}).get('name', '?')

out = dict(
    meta=dict(source='cashew-2026-07-04-18-03-44-147880.sql', txns=len(rows),
              ops=len(ops), transfers=len(xfers), usd_pkr=USD_PKR,
              period=[days[0], days[-1]]),
    monthly=monthly, treemap=treemap, calendar=calendar,
    balance=dict(months=bmonths, wallets=wnames,
                 series=series, networth=networth),
    sankey=sankey,
    kpi=dict(total_expense=round(total_exp), total_income=round(total_inc),
             net=round(total_inc - total_exp),
             si_count=len(si), si_value=round(sum(r['base'] for r in si)),
             pi_count=len(pi), pi_value=round(sum(r['base'] for r in pi)),
             je_count=len(je), je_value=round(sum(r['base'] for r in je))),
    goals=goals, budgets=budgets, by_month=by_month,
)
print(json.dumps(out))
