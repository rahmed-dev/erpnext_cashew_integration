# f012 dashboard demo — visual reference for the build

Approved by the user 2026-08-07. **This is the visual spec.** When building the
real components, match this layout, density, palette, and chart configuration
unless a decision in `../arch/decisions.md` says otherwise.

Live artifact: <https://claude.ai/code/artifact/bfaa1d08-c184-48a5-978d-1c542389236f>

> **Two corrections from the 2026-08-07 pre-dev coherence pass. Read these
> before copying anything out of the demo.**
>
> 1. **Do not port the light/dark toggle.** The demo has one because an
>    artifact renders in the viewer's theme. The SPA has **zero** `dark:`
>    utilities and no dark handling in `theme.js`. Dark mode is out of scope
>    for f012 (`arch/decisions.md` C5.6); porting the toggle ships a half-dark
>    dashboard inside an all-light application.
> 2. **`aggregate_from_backup.py` scopes "Food outdoor" to the wrong wallet.**
>    It reads the scalar `budgets.wallet_fk`. The scope is `wallet_fks`, and
>    NULL there means *all wallets* (C5.1). The product must use the C5.2
>    matching rule, which also adds the `category_fks_exclude` list the script
>    omits entirely.
>
> The backup the demo was built from, `cashew-2026-07-04-…sql`, no longer
> exists on disk. The current export is
> `cashew-2026-08-07-00-20-33-593933.sql` (652 transactions). Regenerating
> `demo-data.json` against it is optional — the demo's job is the visual spec,
> not the numbers.

## What is here

| file | what it is |
|---|---|
| `dashboard-demo.template.html` | markup + token CSS (light and dark) |
| `dashboard-demo.app.js` | every ECharts option object, the period filter, the theme switch |
| `aggregate_from_backup.py` | reads a Cashew SQLite backup and emits the chart datasets |
| `demo-data.json` | output of the above against `cashew-2026-07-04-18-03-44-147880.sql` |

The published artifact is these four spliced together with `echarts.min.js`
inlined (Artifact CSP blocks CDNs). The 1 MB spliced file is deliberately not
committed — rebuild it instead.

## Rebuild

```sh
npm pack echarts@5 && tar xzf echarts-5.6.0.tgz package/dist/echarts.min.js
python3 aggregate_from_backup.py > demo-data.json     # edit DB path at the top
python3 - <<'EOF'
tpl = open('dashboard-demo.template.html').read()
out = (tpl.replace('/*ECHARTS*/', open('package/dist/echarts.min.js').read())
          .replace('/*DATA*/', open('demo-data.json').read().strip())
          .replace('/*APP*/', open('dashboard-demo.app.js').read()))
open('demo.html', 'w').write(out)
EOF
```

## What the demo is faithful about

- Every number comes from the real 2026-07-04 backup — 552 paid transactions,
  487 income/expense, 65 transfers, real category and account names.
- All seven charts from Decision 3, in the frappe-ui visual language the SPA
  already uses: indigo accent, `rounded-lg` cards, compact type, sidebar shell.
- The locked 10-hue categorical ramp from Decision 4, in both themes.
- Light and dark, driven by tokens with a working toggle.
- **The period control works** and demonstrates D3.d: pick "All time" or
  "Last 6 months" and both budgets render per-cycle against their limit line;
  pick "Latest month" and the savings budget collapses to the gauge and the
  spending limit to a single bar. Every other chart re-aggregates too.
- A cycle with no matching transactions renders as 0, not as a gap — a month
  where nothing was saved is a missed target, not missing data.
- The savings goal and spending limit are your **real Cashew budgets** (D3.a-ter),
  matched by category, account, and direction — Savings 50,000/month on the
  Saving account, Food outdoor 10,000/month on Entertainment.
- The negative net-worth stretch through late 2025 is real, and the demo says so
  in a notice strip rather than hiding it. See the opening-balance caveat in
  `../arch/decisions.md`.

## What the demo fakes, and must not be copied

1. **USD conversion is a flat 278 PKR.** The real dashboard uses each row's
   actual transacted rate — see the "Exchange Rate Source of Truth" decision in
   `../../../system-arch/decisions-log.md`.
2. **Aggregation runs client-side over the raw backup.** In the product every
   number comes from `dashboard_summary` over GL Entry, which is the accounting
   truth — the demo reads Cashew directly and will not agree with GL where an
   import errored, was reverted, or posted at a different rate.
3. **Period and company selectors are inert.** They exist to show the chrome.
4. **The font is a system stack.** The SPA uses frappe-ui's Inter.
5. **Budget cycles are hardcoded to calendar months.** The demo buckets on the
   dashboard's own months. The product buckets on each budget's own anchor and
   `reoccurrence` + `period_length` (D3.d), computed server-side (C5.8) — a
   weekly budget over a three-month filter yields ~13 marks, not 3.
   *(The open question this entry used to carry — pro-rate the target or show
   the latest cycle — was closed by D3.d: never pro-rate. The cycle is the
   unit; the filter selects how many are shown.)*
6. **The savings and limit figures use the demo's own matching rule**, which
   reads the scalar `wallet_fk` and ignores `category_fks_exclude`. See the
   correction at the top.

## Build notes worth keeping

- **zrender does not understand CSS `color-mix()`.** Translucent fills must be
  built as `rgba()` from the token hex — see the `alpha()` helper in the
  template. Handing ECharts a `color-mix()` string renders black with no error.
- Charts re-read their CSS tokens on theme change and are rebuilt with
  `setOption(opt, true)`. Tokens cannot be passed once at init.
- The calendar heatmap needs one `calendar` + one `series` entry per year, and
  its `visualMap` max is set at the 94th percentile so a few outlier days do not
  flatten the whole scale.
- Resize is debounced at 120 ms across all instances.
