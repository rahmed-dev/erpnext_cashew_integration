// Cashew SPA — Finance Dashboard.
// QuickBooks-inspired tile-forward layout with restrained Stripe-y palette.

const { Icon, StatusPill, AmountDisplay, Tile, EmptyState, Skel, MiniBar, Shell, PageHeader } = window;

// ── Period Selector (pill dropdown) ────────────────────────────────────────
const PERIOD_PRESETS = ['This Month', 'Last Month', 'Last 30 Days', 'Last 90 Days', 'This Fiscal Year', 'Custom Range…'];

const PeriodSelector = ({ value = 'This Month', onChange, loading }) => {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <button className="cs-chip" onClick={() => setOpen(o => !o)}>
        <Icon name="calendar" size={14} color="var(--cs-text-2)" />
        <span style={{ fontWeight: 500 }}>{value}: <span style={{ color: 'var(--cs-text)' }}>May 2026</span></span>
        {loading && <Icon name="loader" size={12} style={{ animation: 'cs-pulse 1s linear infinite' }}/>}
        <Icon name="chevron-down" size={14} color="var(--cs-text-2)" />
      </button>
      {open && (
        <div className="cs-card" style={{ position: 'absolute', top: 'calc(100% + 6px)', right: 0, zIndex: 10, padding: 4, minWidth: 200, boxShadow: 'var(--cs-shadow-lg)' }}
             onMouseLeave={() => setOpen(false)}>
          {PERIOD_PRESETS.map(p => (
            <button key={p} onClick={() => { onChange?.(p); setOpen(false); }}
                    style={{ display:'block', width:'100%', padding:'7px 10px', border:0, background: p === value ? 'var(--cs-accent-50)' : 'transparent',
                             color: p === value ? 'var(--cs-accent-700)' : 'var(--cs-text)', borderRadius: 5, fontSize: 13, textAlign:'left', cursor: 'pointer' }}>
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// ── Donut chart (SVG) ──────────────────────────────────────────────────────
const DonutChart = ({ income, expense, currency = 'PKR', size = 200 }) => {
  const total = income + expense;
  const incPct = total ? income / total : 0.5;
  const expPct = total ? expense / total : 0.5;
  const r = size / 2 - 22;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const incLen = circ * incPct;
  const expLen = circ * expPct;
  const net = income - expense;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      {/* background ring */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--cs-line-2)" strokeWidth="24"/>
      {/* income — green */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#16a34a" strokeWidth="24"
              strokeDasharray={`${incLen} ${circ - incLen}`} strokeDashoffset={circ/4} transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt"/>
      {/* expense — red, starting where income ended */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#dc2626" strokeWidth="24"
              strokeDasharray={`${expLen} ${circ - expLen}`} strokeDashoffset={circ/4 - incLen} transform={`rotate(-90 ${cx} ${cy})`} strokeLinecap="butt"/>
      {/* center label */}
      <text x={cx} y={cy - 8} textAnchor="middle" fontSize="10" fill="var(--cs-text-3)" style={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>Net</text>
      <text x={cx} y={cy + 14} textAnchor="middle" fontSize="20" fontWeight="600" fill={net >= 0 ? '#15803d' : '#b91c1c'} style={{ fontVariantNumeric: 'tabular-nums' }}>
        {window.fmtPKR(net, { compact: true })}
      </text>
      <text x={cx} y={cy + 32} textAnchor="middle" fontSize="10" fill="var(--cs-text-3)">{net >= 0 ? '↑ surplus' : '↓ deficit'}</text>
    </svg>
  );
};

// ── Bar chart variant ──────────────────────────────────────────────────────
const BarChart = ({ income, expense }) => {
  const max = Math.max(income, expense);
  const inc = (income / max) * 100;
  const exp = (expense / max) * 100;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 28, height: 200, padding: '12px 24px 24px', justifyContent: 'center' }}>
      {[
        { label: 'Income',  pct: inc, color: '#16a34a', amount: income },
        { label: 'Expense', pct: exp, color: '#dc2626', amount: expense },
      ].map((b, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, height: '100%' }}>
          <div style={{ fontSize: 11, color: 'var(--cs-text-3)', fontVariantNumeric: 'tabular-nums' }}>{window.fmtPKR(b.amount, { compact: true })}</div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end' }}>
            <div style={{ width: 64, background: b.color, height: `${b.pct}%`, borderRadius: '6px 6px 0 0', minHeight: 4 }} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--cs-text-2)', fontWeight: 500 }}>{b.label}</div>
        </div>
      ))}
    </div>
  );
};

// ── IncomeExpenseChart card ───────────────────────────────────────────────
const IncomeExpenseChart = ({ data, chartStyle = 'donut' }) => {
  return (
    <div className="cs-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Income vs Expense</h3>
          <div style={{ fontSize: 12, color: 'var(--cs-text-3)', marginTop: 2 }}>May 1 – May 24, 2026</div>
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
          <div style={{ display:'flex', alignItems:'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: '#16a34a' }} />
            <span style={{ color: 'var(--cs-text-2)' }}>Income</span>
            <span style={{ fontWeight: 600 }} className="cs-num">{window.fmtPKR(data.income_total, { compact: true })}</span>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: '#dc2626' }} />
            <span style={{ color: 'var(--cs-text-2)' }}>Expense</span>
            <span style={{ fontWeight: 600 }} className="cs-num">{window.fmtPKR(data.expense_total, { compact: true })}</span>
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 220 }}>
        {chartStyle === 'donut'
          ? <DonutChart income={data.income_total} expense={data.expense_total} />
          : <BarChart income={data.income_total} expense={data.expense_total} />}
      </div>
    </div>
  );
};

// ── Category breakdown ────────────────────────────────────────────────────
const CategoryList = ({ title, rows, accent }) => {
  const max = rows.length ? Math.max(...rows.map(r => r.amount)) : 1;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 11, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, paddingBottom: 4 }}>
        {title}
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0' }}>
          <div style={{ flex: '0 0 130px', fontSize: 13, color: 'var(--cs-text)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{r.category}</div>
          <div style={{ flex: 1 }}>
            <MiniBar value={r.amount} max={max} color={accent} height={6}/>
          </div>
          <div style={{ flex: '0 0 auto', fontSize: 13, fontWeight: 500 }} className="cs-num">
            {window.fmtPKR(r.amount, { compact: true })}
          </div>
        </div>
      ))}
    </div>
  );
};

const CategoryBreakdownCard = ({ data }) => (
  <div className="cs-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Top Categories</h3>
      <div style={{ fontSize: 12, color: 'var(--cs-text-3)', marginTop: 2 }}>May 1 – May 24, 2026</div>
    </div>
    <CategoryList title="Income"  rows={data.income_by_category}  accent="#16a34a" />
    <div style={{ height: 1, background: 'var(--cs-line-2)' }} />
    <CategoryList title="Expense" rows={data.expense_by_category} accent="#dc2626" />
  </div>
);

// ── Recent imports strip ───────────────────────────────────────────────────
const ImportCard = ({ run, onClick }) => (
  <div className="cs-card" data-clickable onClick={onClick}
       style={{ minWidth: 240, flex: '0 0 240px', padding: 14, display: 'flex', flexDirection: 'column', gap: 8, cursor: 'pointer', transition: 'transform .12s, box-shadow .12s' }}
       onMouseEnter={(e) => { e.currentTarget.style.boxShadow = 'var(--cs-shadow-md)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
       onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'var(--cs-shadow)'; e.currentTarget.style.transform = 'none'; }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: 11, color: 'var(--cs-text-2)' }}>{run.name}</span>
      <StatusPill kind="run-status" value={run.status} size="sm" />
    </div>
    <div style={{ fontSize: 13, color: 'var(--cs-text)' }}>{window.fmtRange(run.period_start, run.period_end)}</div>
    <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--cs-text-2)' }}>
      <span><span style={{ color: 'var(--cs-green)', fontWeight: 600 }} className="cs-num">{run.rows_valid}</span> valid</span>
      {run.rows_failed > 0 && <span><span style={{ color: 'var(--cs-red)', fontWeight: 600 }} className="cs-num">{run.rows_failed}</span> failed</span>}
      {run.rows_posted > 0 && <span><Icon name="check" size={11} color="var(--cs-green)" style={{ verticalAlign: 'middle' }}/> <span className="cs-num">{run.rows_posted}</span> posted</span>}
    </div>
    <div style={{ fontSize: 11, color: 'var(--cs-text-3)', marginTop: 'auto' }}>Updated {window.relTime(run.modified)}</div>
  </div>
);

const RecentImportsStrip = ({ runs, onPick }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Recent Imports</h3>
      <a className="cs-link" style={{ fontSize: 13 }}>View all imports →</a>
    </div>
    <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 4 }}>
      {runs.map(r => <ImportCard key={r.name} run={r} onClick={() => onPick?.(r)} />)}
    </div>
  </div>
);

// ── Loading-state tiles ────────────────────────────────────────────────────
const TileSkeleton = () => (
  <div className="cs-card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
    <Skel w="50%" h={12} />
    <Skel w="70%" h={26} />
    <Skel w="35%" h={11} />
  </div>
);

// ── Main page ──────────────────────────────────────────────────────────────
const FinanceDashboard = ({ state = 'loaded', chartStyle = 'donut', onPickRun }) => {
  const data = window.CASHEW_DATA.DASHBOARD;
  const [period, setPeriod] = React.useState('This Month');
  const [loading, setLoading] = React.useState(false);
  const change = (p) => { setLoading(true); setPeriod(p); setTimeout(() => setLoading(false), 600); };

  if (state === 'empty') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <PageHeader title="Finance Dashboard" actions={<PeriodSelector value={period} onChange={change} loading={loading}/>}/>
        <div style={{ flex: 1, display:'flex', alignItems:'center', justifyContent: 'center', padding: 28 }}>
          <EmptyState icon="bar-chart-2"
            title="Nothing to show for this period."
            body="Once Cashew imports are posted to the General Ledger, totals and charts will appear here. Run your first import to get started."
            primary={{ label: 'Start an Import' }}
            secondary={{ label: 'Change period' }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Finance Dashboard"
        subtitle={`Karachi Trading Co. · ${window.fmtRange(data.period.start, data.period.end)}`}
        actions={<>
          <button className="cs-btn"><Icon name="refresh" size={14}/></button>
          <PeriodSelector value={period} onChange={change} loading={loading || state === 'loading'} />
        </>}
      />
      <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Tile grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
          {state === 'loading' ? (
            <><TileSkeleton/><TileSkeleton/><TileSkeleton/><TileSkeleton/></>
          ) : <>
            <Tile icon="wallet"            label="Cash & Bank"      amount={data.balance_tiles.cash_bank.amount}      prior={data.balance_tiles.cash_bank.prior_amount}  accent="#0891b2" />
            <Tile icon="arrow-down-circle" label="Receivable"       amount={data.balance_tiles.receivable.amount}     prior={data.balance_tiles.receivable.prior_amount} accent="#16a34a" />
            <Tile icon="arrow-up-circle"   label="Payable"          amount={data.balance_tiles.payable.amount}        prior={data.balance_tiles.payable.prior_amount}    accent="#dc2626" />
            <Tile icon="trending-up"       label="Net This Period"  amount={data.balance_tiles.net_for_period.amount} accent="#4f46e5" />
          </>}
        </div>

        {/* Chart + categories */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 14, alignItems: 'stretch' }}
             className="cs-dash-mid">
          {state === 'loading' ? <>
            <div className="cs-card" style={{ padding: 20, minHeight: 280 }}><Skel w="100%" h={240} style={{ display: 'block' }} /></div>
            <div className="cs-card" style={{ padding: 20, minHeight: 280 }}>
              <Skel w="40%" h={14} style={{ display: 'block', marginBottom: 12 }} />
              {[...Array(5)].map((_, i) => <div key={i} style={{ display:'flex', gap:8, marginBottom: 8 }}><Skel w="40%" h={12}/><Skel w="100%" h={6}/></div>)}
            </div>
          </> : <>
            <IncomeExpenseChart data={data} chartStyle={chartStyle} />
            <CategoryBreakdownCard data={data} />
          </>}
        </div>

        {/* Recent imports */}
        {state !== 'loading' && <RecentImportsStrip runs={data.recent_runs} onPick={onPickRun}/>}
      </div>
      {/* Force chart+categories to stack on narrow content area */}
      <style>{`
        @container (max-width: 880px) { .cs-dash-mid { grid-template-columns: 1fr !important; } }
        @media (max-width: 880px)     { .cs-dash-mid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  );
};

Object.assign(window, { FinanceDashboard });
