// Cashew SPA — Imports List page.
// Stripe/Linear-style table; FilterBar; pagination; mobile-card fallback.

const { Icon, StatusPill, EmptyState, Skel, Shell, PageHeader } = window;

const FilterChip = ({ label, value, onClick, active, withChevron = true }) => (
  <button className={`cs-chip ${active ? 'cs-chip-active' : ''}`} onClick={onClick}>
    {label}{value && <span style={{ fontWeight: 600, color: active ? 'var(--cs-accent-700)' : 'var(--cs-text)' }}>: {value}</span>}
    {withChevron && <Icon name="chevron-down" size={12}/>}
  </button>
);

// Multi-select status filter dropdown
const StatusFilterDD = ({ value, onChange }) => {
  const [open, setOpen] = React.useState(false);
  const all = ['Draft','Parsed','Validated','Queued','Processing','Completed','Failed','Cancelled','Reverted','Revert-Failed'];
  return (
    <div style={{ position: 'relative' }}>
      <FilterChip label="Status" value={value.length ? `${value.length} selected` : null} active={value.length > 0} onClick={() => setOpen(o => !o)} />
      {open && (
        <div className="cs-card" style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 10, padding: 6, minWidth: 200, boxShadow: 'var(--cs-shadow-lg)' }} onMouseLeave={() => setOpen(false)}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 8px 8px', borderBottom: '1px solid var(--cs-line-2)', marginBottom: 4 }}>
            <button className="cs-link" style={{ fontSize: 12, background:'none', border:0, padding:0, cursor:'pointer' }} onClick={() => onChange(all.slice())}>Select all</button>
            <button className="cs-link" style={{ fontSize: 12, background:'none', border:0, padding:0, cursor:'pointer' }} onClick={() => onChange([])}>Clear</button>
          </div>
          {all.map(s => {
            const checked = value.includes(s);
            return (
              <label key={s} style={{ display:'flex', alignItems:'center', gap: 8, padding: '5px 8px', cursor: 'pointer', borderRadius: 4 }}
                     onMouseEnter={e => e.currentTarget.style.background = 'var(--cs-bg-2)'}
                     onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <input type="checkbox" checked={checked} onChange={() => onChange(checked ? value.filter(v => v !== s) : [...value, s])} />
                <StatusPill kind="run-status" value={s} size="sm" />
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Sortable column header
const Th = ({ children, sortKey, sort, onSort, align = 'left', width }) => {
  const active = !!sortKey && sort?.key === sortKey;
  const dir = active ? sort.dir : null;
  return (
    <th onClick={sortKey ? () => onSort(sortKey) : undefined}
        style={{ textAlign: align, width, cursor: sortKey ? 'pointer' : 'default', userSelect: 'none' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: active ? 'var(--cs-text)' : 'inherit' }}>
        {children}
        {active && <Icon name={dir === 'desc' ? 'chevron-down' : 'chevron-up'} size={11} />}
      </span>
    </th>
  );
};

const KebabMenu = ({ items }) => {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <button className="cs-btn cs-btn-ghost" style={{ padding: 4 }} onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}>
        <Icon name="more-vertical" size={16}/>
      </button>
      {open && (
        <div className="cs-card" onMouseLeave={() => setOpen(false)} onClick={(e) => e.stopPropagation()}
             style={{ position: 'absolute', top: 'calc(100% + 4px)', right: 0, zIndex: 20, padding: 4, minWidth: 200, boxShadow: 'var(--cs-shadow-lg)' }}>
          {items.map((it, i) => it.divider ? (
            <div key={i} style={{ height: 1, background: 'var(--cs-line-2)', margin: '4px 0' }}/>
          ) : (
            <button key={i} onClick={(e) => { e.stopPropagation(); it.action?.(); setOpen(false); }}
                    style={{ display:'flex', alignItems:'center', gap: 8, width: '100%', padding: '7px 10px', border: 0, background: 'transparent',
                             color: it.danger ? 'var(--cs-red)' : 'var(--cs-text)', fontSize: 13, cursor: 'pointer', textAlign: 'left', borderRadius: 4 }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--cs-bg-2)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              {it.icon && <Icon name={it.icon} size={14}/>}
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// Mobile card variant of a run row
const RunMobileCard = ({ run, onClick }) => (
  <div className="cs-card" data-clickable onClick={onClick} style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8, cursor: 'pointer' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <span style={{ fontFamily:'ui-monospace, monospace', fontSize: 12, color: 'var(--cs-text)' }}>{run.name}</span>
      <StatusPill kind="run-status" value={run.status} size="sm"/>
    </div>
    <div style={{ fontSize: 13, color: 'var(--cs-text-2)' }}>{window.fmtRange(run.period_start, run.period_end)}</div>
    <div style={{ display: 'flex', gap: 14, fontSize: 12, color: 'var(--cs-text-2)' }}>
      <span><b className="cs-num" style={{ color: 'var(--cs-text)' }}>{run.rows_total}</b> total</span>
      <span><b className="cs-num" style={{ color: 'var(--cs-green)' }}>{run.rows_valid}</b> valid</span>
      {run.rows_failed > 0 && <span><b className="cs-num" style={{ color: 'var(--cs-red)' }}>{run.rows_failed}</b> failed</span>}
      <span><b className="cs-num">{run.rows_posted}</b> posted</span>
    </div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--cs-text-3)', marginTop: 2 }}>
      <span>{run.company}</span>
      <span>Updated {window.relTime(run.modified)}</span>
    </div>
  </div>
);

// ── Main page ──────────────────────────────────────────────────────────────
const ImportsList = ({ state = 'loaded', onOpenRun, onNew }) => {
  const all = window.CASHEW_DATA.RUNS_LIST;
  const [statusFilter, setStatusFilter] = React.useState([]);
  const [search, setSearch] = React.useState('');
  const [sort, setSort] = React.useState({ key: 'modified', dir: 'desc' });
  const [page, setPage] = React.useState(1);
  const PAGE_SIZE = 8;

  // Filter + sort
  let filtered = all.filter(r => {
    if (statusFilter.length && !statusFilter.includes(r.status)) return false;
    if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
  filtered.sort((a, b) => {
    const av = a[sort.key], bv = b[sort.key];
    if (av < bv) return sort.dir === 'asc' ? -1 : 1;
    if (av > bv) return sort.dir === 'asc' ? 1 : -1;
    return 0;
  });

  const total = filtered.length;
  const start = (page - 1) * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleSort = (key) => {
    setSort(s => s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' });
  };

  const clearAll = () => { setStatusFilter([]); setSearch(''); };
  const anyFilter = statusFilter.length > 0 || search.length > 0;

  if (state === 'empty') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <PageHeader title="Imports" actions={<button className="cs-btn cs-btn-primary" onClick={onNew}><Icon name="plus" size={14}/> New Import</button>}/>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 28 }}>
          <EmptyState icon="file-text"
            title="No imports yet."
            body="Start your first Cashew import by uploading a CSV from the Cashew app's export."
            primary={{ label: 'Start an Import' }}
            secondary={{ label: 'Configure mappings →' }} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title="Imports"
        subtitle={`${all.length} runs total`}
        actions={<>
          <div style={{ position: 'relative' }}>
            <Icon name="search" size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--cs-text-3)' }}/>
            <input className="cs-input" placeholder="Search by run name…" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
                   style={{ paddingLeft: 30, width: 240 }}/>
          </div>
          <button className="cs-btn cs-btn-primary" onClick={onNew}><Icon name="plus" size={14}/> New Import</button>
        </>}
      />

      {/* Filter bar */}
      <div style={{ padding: '12px 28px', borderBottom: '1px solid var(--cs-line)', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', background: 'var(--cs-bg)' }}>
        <StatusFilterDD value={statusFilter} onChange={(v) => { setStatusFilter(v); setPage(1); }} />
        <FilterChip label="Period" value="Any" onClick={() => {}} />
        <FilterChip label="Company" value="All" onClick={() => {}} />
        {anyFilter && (
          <button className="cs-btn cs-btn-ghost cs-btn-sm" onClick={clearAll} style={{ marginLeft: 'auto' }}>
            <Icon name="x" size={12}/> Clear filters
          </button>
        )}
      </div>

      {/* Active filter chips */}
      {statusFilter.length > 0 && (
        <div style={{ padding: '8px 28px', display: 'flex', gap: 6, flexWrap: 'wrap', borderBottom: '1px solid var(--cs-line-2)' }}>
          {statusFilter.map(s => (
            <span key={s} style={{ display:'inline-flex', alignItems:'center', gap: 4, padding: '3px 4px 3px 8px', background: 'var(--cs-accent-50)', color: 'var(--cs-accent-700)', borderRadius: 6, fontSize: 12 }}>
              Status: {s}
              <button onClick={() => setStatusFilter(statusFilter.filter(x => x !== s))} style={{ border:0, background:'transparent', padding: 2, cursor: 'pointer', display:'flex', color:'var(--cs-accent-700)' }}>
                <Icon name="x" size={11}/>
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Table or cards */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 28px' }}>
        {/* Empty filter result */}
        {pageRows.length === 0 && state !== 'loading' && (
          <div style={{ padding: 48, textAlign: 'center' }}>
            <div style={{ fontSize: 14, color: 'var(--cs-text-2)', marginBottom: 12 }}>No runs match these filters.</div>
            <button className="cs-btn" onClick={clearAll}>Clear filters</button>
          </div>
        )}

        {state === 'loading' ? (
          <div style={{ padding: '16px 0' }}>
            {[...Array(6)].map((_, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 0', borderBottom: '1px solid var(--cs-line-2)' }}>
                <Skel w={140} h={14}/><Skel w={90} h={20}/><Skel w={140} h={14}/><Skel w={60} h={14}/><Skel w={60} h={14}/><Skel w={60} h={14}/><Skel w={80} h={14}/>
              </div>
            ))}
          </div>
        ) : pageRows.length > 0 && (
          <>
            {/* Desktop table */}
            <table className="cs-table cs-runs-table" style={{ marginTop: 0 }}>
              <thead>
                <tr>
                  <Th>Run</Th>
                  <Th sortKey="status" sort={sort} onSort={toggleSort}>Status</Th>
                  <Th>Company</Th>
                  <Th sortKey="period_start" sort={sort} onSort={toggleSort}>Period</Th>
                  <Th align="right">Total</Th>
                  <Th align="right">Valid</Th>
                  <Th align="right">Failed</Th>
                  <Th align="right">Posted</Th>
                  <Th sortKey="modified" sort={sort} onSort={toggleSort}>Updated</Th>
                  <Th width={40}></Th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r, i) => (
                  <tr key={r.name} data-clickable onClick={() => onOpenRun?.(r)} style={{ cursor: 'pointer' }}>
                    <td style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12, color: 'var(--cs-text)' }}>{r.name}</td>
                    <td><StatusPill kind="run-status" value={r.status} size="sm" /></td>
                    <td style={{ color: 'var(--cs-text-2)' }}>{r.company}</td>
                    <td style={{ color: 'var(--cs-text-2)' }}>{window.fmtRange(r.period_start, r.period_end)}</td>
                    <td align="right" className="cs-num">{r.rows_total}</td>
                    <td align="right" className="cs-num" style={{ color: r.rows_valid === r.rows_total && r.rows_total > 0 ? 'var(--cs-green)' : 'inherit', fontWeight: 500 }}>{r.rows_valid}</td>
                    <td align="right" className="cs-num" style={{ color: r.rows_failed > 0 ? 'var(--cs-red)' : 'var(--cs-text-3)', fontWeight: r.rows_failed > 0 ? 600 : 400 }}>{r.rows_failed || '—'}</td>
                    <td align="right" className="cs-num">{r.rows_posted}</td>
                    <td style={{ color: 'var(--cs-text-2)', fontSize: 12 }} title={r.modified}>{window.relTime(r.modified)}</td>
                    <td>
                      <KebabMenu items={[
                        { label: 'Open workspace', icon: 'arrow-right', action: () => onOpenRun?.(r) },
                        { label: 'Open in Desk',   icon: 'external-link' },
                        { divider: true },
                        r.status === 'Completed' && { label: 'Revert', icon: 'rotate-ccw', danger: true },
                        ['Queued','Processing'].includes(r.status) && { label: 'Cancel', icon: 'x', danger: true },
                        ['Completed','Failed','Revert-Failed'].includes(r.status) && { label: 'Download diagnostics CSV', icon: 'download' },
                      ].filter(Boolean)}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div style={{ padding: '16px 0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: 12, color: 'var(--cs-text-2)' }}>Showing {start + 1}–{Math.min(start + PAGE_SIZE, total)} of {total}</div>
              <div style={{ display: 'flex', gap: 4 }}>
                <button className="cs-btn cs-btn-sm" onClick={() => setPage(p => Math.max(1, p-1))} disabled={page === 1}><Icon name="chevron-left" size={12}/></button>
                {[...Array(totalPages)].map((_, i) => (
                  <button key={i} className={`cs-btn cs-btn-sm ${i+1 === page ? 'cs-btn-primary' : ''}`} onClick={() => setPage(i + 1)} style={{ minWidth: 28 }}>{i+1}</button>
                ))}
                <button className="cs-btn cs-btn-sm" onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page === totalPages}><Icon name="chevron-right" size={12}/></button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

Object.assign(window, { ImportsList, KebabMenu });
