// Alternate layouts — opinionated proposals beyond spec.
// 1) "Single-row finance bar" dashboard — denser, Linear-like
// 2) "Split workbench" — permanent row detail drawer on the right
// Both are SPEC-FAITHFUL in data + actions; they re-arrange the layout.

const { Icon, StatusPill, AmountDisplay, MiniBar, Skel, PageHeader, CashewMark } = window;

// ── ALT 1: Single-bar dashboard ───────────────────────────────────────────
const DashboardAlt = () => {
  const d = window.CASHEW_DATA.DASHBOARD;
  const items = [
    { label: 'Cash & Bank',  value: d.balance_tiles.cash_bank.amount,  prior: d.balance_tiles.cash_bank.prior_amount,  color: '#0891b2' },
    { label: 'Receivable',   value: d.balance_tiles.receivable.amount, prior: d.balance_tiles.receivable.prior_amount, color: '#16a34a' },
    { label: 'Payable',      value: d.balance_tiles.payable.amount,    prior: d.balance_tiles.payable.prior_amount,    color: '#dc2626' },
    { label: 'Income MTD',   value: d.income_total,                    color: '#16a34a' },
    { label: 'Expense MTD',  value: d.expense_total,                   color: '#dc2626' },
    { label: 'Net MTD',      value: d.balance_tiles.net_for_period.amount, color: '#4f46e5' },
  ];
  return (
    <div className="cs-root" style={{ height: '100%', background: 'var(--cs-bg)', display: 'flex', flexDirection: 'column' }}>
      <PageHeader title="Finance Dashboard" subtitle="Karachi Trading Co. · May 1 – May 24, 2026"/>
      <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Single horizontal stat bar */}
        <div className="cs-card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${items.length}, minmax(140px, 1fr))` }}>
            {items.map((it, i) => {
              const delta = it.prior != null ? ((it.value - it.prior) / Math.abs(it.prior)) * 100 : null;
              return (
                <div key={i} style={{ padding: '16px 18px', borderRight: i < items.length - 1 ? '1px solid var(--cs-line-2)' : 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 6, height: 6, borderRadius: 999, background: it.color }} />
                    <span style={{ fontSize: 11, color: 'var(--cs-text-2)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>{it.label}</span>
                  </div>
                  <div className="cs-num" style={{ fontSize: 19, fontWeight: 600, letterSpacing: '-0.01em' }}>{window.fmtPKR(it.value, { compact: true })}</div>
                  {delta != null && (
                    <div style={{ fontSize: 11, color: delta >= 0 ? 'var(--cs-green)' : 'var(--cs-red)', display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Icon name={delta >= 0 ? 'trending-up' : 'trending-down'} size={11}/> {Math.abs(delta).toFixed(1)}%
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Ledger-style table view of categories — replaces the donut + lists */}
        <div className="cs-card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Category P&amp;L</h3>
            <div style={{ display: 'flex', gap: 6, fontSize: 12 }}>
              <button className="cs-chip cs-chip-active" style={{ padding: '3px 8px' }}>Combined</button>
              <button className="cs-chip" style={{ padding: '3px 8px' }}>Income only</button>
              <button className="cs-chip" style={{ padding: '3px 8px' }}>Expense only</button>
            </div>
          </div>
          <table className="cs-table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>Side</th>
                <th>Category</th>
                <th>Share</th>
                <th align="right" style={{ width: 140 }}>Amount</th>
                <th align="right" style={{ width: 80 }}>% of side</th>
              </tr>
            </thead>
            <tbody>
              {d.income_by_category.map((c, i) => {
                const max = Math.max(...d.income_by_category.map(x => x.amount));
                const pct = (c.amount / d.income_total) * 100;
                return (
                  <tr key={'i'+i}>
                    <td><StatusPill kind="txn-type" value="Income" size="sm"/></td>
                    <td>{c.category}</td>
                    <td><MiniBar value={c.amount} max={max} color="#16a34a"/></td>
                    <td align="right"><AmountDisplay amount={c.amount}/></td>
                    <td align="right" className="cs-num" style={{ color: 'var(--cs-text-2)' }}>{pct.toFixed(1)}%</td>
                  </tr>
                );
              })}
              {d.expense_by_category.map((c, i) => {
                const max = Math.max(...d.expense_by_category.map(x => x.amount));
                const pct = (c.amount / d.expense_total) * 100;
                return (
                  <tr key={'e'+i}>
                    <td><StatusPill kind="txn-type" value="Expense" size="sm"/></td>
                    <td>{c.category}</td>
                    <td><MiniBar value={c.amount} max={max} color="#dc2626"/></td>
                    <td align="right"><AmountDisplay amount={c.amount}/></td>
                    <td align="right" className="cs-num" style={{ color: 'var(--cs-text-2)' }}>{pct.toFixed(1)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ── ALT 2: Split workbench — collapsible row drawer ───────────────────────
const WorkbenchSplitAlt = () => {
  const ROWS = window.CASHEW_DATA.ROWS;
  const [selectedIdx, setSelectedIdx] = React.useState(9); // start on an Error row
  const [drawerOpen, setDrawerOpen] = React.useState(true);
  const visible = ROWS.slice(0, 18);
  const row = ROWS.find(r => r.row_idx === selectedIdx) || ROWS[0];

  const gotoRow = (delta) => {
    const idx = visible.findIndex(r => r.row_idx === selectedIdx);
    const next = visible[(idx + delta + visible.length) % visible.length];
    if (next) setSelectedIdx(next.row_idx);
  };

  const onRowClick = (idx) => {
    setSelectedIdx(idx);
    if (!drawerOpen) setDrawerOpen(true); // re-open if user clicks a row while collapsed
  };

  return (
    <div className="cs-root" style={{ height: '100%', background: 'var(--cs-bg)', display: 'flex', flexDirection: 'column' }}>
      <PageHeader title="CSH-IMP-2026-000016 · Workbench" subtitle="Karachi Trading Co. · 36 rows · 4 errors"
                  actions={<>
                    <button className="cs-btn"><Icon name="filter" size={13}/> Filters</button>
                    <button className={`cs-btn ${drawerOpen ? '' : 'cs-btn-ghost'}`} onClick={() => setDrawerOpen(o => !o)}
                            title={drawerOpen ? 'Collapse detail panel' : 'Show detail panel'}>
                      <Icon name={drawerOpen ? 'chevron-right' : 'chevron-left'} size={13}/>
                      {drawerOpen ? 'Hide detail' : 'Show detail'}
                    </button>
                    <button className="cs-btn cs-btn-primary">Queue →</button>
                  </>}/>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: drawerOpen ? 'minmax(0, 1fr) 400px' : 'minmax(0, 1fr)', minHeight: 0, transition: 'grid-template-columns .2s ease', position: 'relative' }}>
        {/* Left: rows list */}
        <div style={{ overflow: 'auto', borderRight: drawerOpen ? '1px solid var(--cs-line)' : 'none' }}>
          <table className="cs-table">
            <thead>
              <tr>
                <th style={{ width: 36 }}>#</th>
                <th style={{ width: 90 }}>Status</th>
                <th style={{ width: 80 }}>Date</th>
                <th>Account</th>
                <th align="right" style={{ width: 120 }}>Amount</th>
                <th>Category</th>
                {!drawerOpen && <th>Party</th>}
                {!drawerOpen && <th>Resolved Account / Error</th>}
              </tr>
            </thead>
            <tbody>
              {visible.map(r => (
                <tr key={r.row_idx} onClick={() => onRowClick(r.row_idx)} style={{
                  cursor: 'pointer',
                  background: drawerOpen && r.row_idx === selectedIdx ? 'var(--cs-accent-50)' : undefined,
                  borderLeft: r.validation_status === 'Error' ? '3px solid var(--cs-red)' : '3px solid transparent',
                }}>
                  <td className="cs-num" style={{ color: 'var(--cs-text-3)' }}>{r.row_idx}</td>
                  <td><StatusPill kind="row-validation" value={r.validation_status} size="sm"/></td>
                  <td>{window.fmtDate(r.txn_date)}</td>
                  <td>{r.raw_account}</td>
                  <td align="right"><AmountDisplay amount={r.base_amount} signed signSource={r.income_flag}/></td>
                  <td>{r.category}</td>
                  {!drawerOpen && <td style={{ fontSize: 12 }}>{r.resolved_party ? <span><span style={{ fontSize: 10, color: 'var(--cs-text-3)' }}>{r.resolved_party_type}: </span>{r.resolved_party}</span> : <span style={{ color: 'var(--cs-text-3)' }}>—</span>}</td>}
                  {!drawerOpen && <td style={{ fontSize: 12, color: r.validation_status === 'Error' ? 'var(--cs-red)' : 'var(--cs-text-3)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.validation_status === 'Error' ? r.validation_error_message : (r.resolved_account || '—')}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right: detail (collapsible) */}
        {drawerOpen && (
          <div style={{ overflow: 'auto', background: 'var(--cs-bg)', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>ROW</div>
                  <div style={{ fontSize: 18, fontWeight: 600 }} className="cs-num">#{row.row_idx}</div>
                </div>
                <div style={{ display: 'flex', gap: 2, marginLeft: 8 }}>
                  <button className="cs-btn cs-btn-ghost" style={{ padding: '4px 6px' }} title="Previous row" onClick={() => gotoRow(-1)}><Icon name="chevron-up" size={13}/></button>
                  <button className="cs-btn cs-btn-ghost" style={{ padding: '4px 6px' }} title="Next row" onClick={() => gotoRow(1)}><Icon name="chevron-down" size={13}/></button>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <StatusPill kind="row-validation" value={row.validation_status}/>
                <button className="cs-btn cs-btn-ghost" style={{ padding: 4 }} onClick={() => setDrawerOpen(false)} title="Hide detail (Esc)">
                  <Icon name="x" size={14}/>
                </button>
              </div>
            </div>
            {row.validation_status === 'Error' && (
              <div style={{ padding: 12, background: '#fef2f2', borderRadius: 12, border: '1px solid #fecaca', fontSize: 12, color: '#991b1b' }}>
                <div style={{ fontWeight: 600, marginBottom: 2 }}>{row.validation_error_code}</div>
                {row.validation_error_message}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 12 }}>
              <DetailRow label="Date" value={window.fmtDate(row.txn_date, 'medium')}/>
              <DetailRow label="Type" value={<StatusPill kind="txn-type" value={row.txn_type} size="sm"/>}/>
              <DetailRow label="Account" value={row.raw_account}/>
              <DetailRow label="Amount" value={<span className="cs-num"><AmountDisplay amount={row.base_amount} signed signSource={row.income_flag}/></span>}/>
              <DetailRow label="Category" value={row.category}/>
              <DetailRow label="Sub" value={row.sub_category}/>
            </div>
            <div style={{ height: 1, background: 'var(--cs-line)' }} />
            <div>
              <label style={{ fontSize: 11, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>Resolved Account</label>
              <input className="cs-input" defaultValue={row.resolved_account || ''} placeholder="Search account…" style={{ marginTop: 4 }}/>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <select className="cs-input" defaultValue={row.resolved_party_type || 'Supplier'} style={{ flex: '0 0 110px' }}><option>Customer</option><option>Supplier</option></select>
              <input className="cs-input" defaultValue={row.resolved_party || ''} placeholder="Party…" style={{ flex: 1 }}/>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 'auto', paddingTop: 12 }}>
              <button className="cs-btn cs-btn-primary" style={{ flex: 1 }}><Icon name="check" size={14}/> Save &amp; next →</button>
              <button className="cs-btn"><Icon name="external-link" size={13}/></button>
            </div>
          </div>
        )}

        {/* Edge-rail handle when collapsed — quick re-open */}
        {!drawerOpen && (
          <button onClick={() => setDrawerOpen(true)} title="Show detail panel"
                  style={{
                    position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)',
                    width: 24, height: 60, borderRadius: '8px 0 0 8px',
                    border: '1px solid var(--cs-line)', borderRight: 0,
                    background: 'var(--cs-surface)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: 'var(--cs-shadow-md)', color: 'var(--cs-text-2)',
                  }}>
            <Icon name="chevron-left" size={14}/>
          </button>
        )}
      </div>
    </div>
  );
};

const DetailRow = ({ label, value }) => (
  <div>
    <div style={{ fontSize: 10, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>{label}</div>
    <div style={{ marginTop: 2 }}>{value}</div>
  </div>
);

Object.assign(window, { DashboardAlt, WorkbenchSplitAlt });
