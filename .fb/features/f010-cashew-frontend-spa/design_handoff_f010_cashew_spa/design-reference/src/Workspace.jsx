// Cashew SPA — Run Workspace. Covers all 4 lifecycle states:
//   Draft → Upload | Parsed → Preview | Validated/Queued/Processing → Workbench | terminal → CompletedSummary
//
// Lots of components — kept in one file to share state easily.

const { Icon, StatusPill, AmountDisplay, EmptyState, Skel, MiniBar, Shell, PageHeader, KebabMenu } = window;

// ── State Stepper ──────────────────────────────────────────────────────────
const STEPS = ['Upload', 'Preview', 'Workbench', 'Done'];
const STEP_OF = {
  Draft: 0, Parsed: 1,
  Validated: 2, Queued: 2, Processing: 2,
  Completed: 3, Failed: 3, Cancelled: 3, Reverting: 3, Reverted: 3, 'Revert-Failed': 3,
};

const StateStepper = ({ runStatus }) => {
  const cur = STEP_OF[runStatus] ?? 0;
  return (
    <div style={{ padding: '12px 28px', borderBottom: '1px solid var(--cs-line)', background: 'var(--cs-bg)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {STEPS.map((s, i) => {
          const isCur  = i === cur;
          const isDone = i < cur;
          return (
            <React.Fragment key={s}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  width: 22, height: 22, borderRadius: 999,
                  background: isDone ? 'var(--cs-green)' : isCur ? 'var(--cs-accent)' : 'var(--cs-bg-2)',
                  color: isDone || isCur ? '#fff' : 'var(--cs-text-3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600,
                  boxShadow: isCur ? '0 0 0 4px var(--cs-accent-100)' : 'none',
                }}>
                  {isDone ? <Icon name="check" size={13} color="#fff"/> : i + 1}
                </span>
                <span style={{ fontSize: 13, fontWeight: isCur ? 600 : 400, color: isCur ? 'var(--cs-text)' : isDone ? 'var(--cs-text-2)' : 'var(--cs-text-3)' }}>{s}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{ flex: '0 1 60px', height: 1, background: i < cur ? 'var(--cs-green)' : 'var(--cs-line)', minWidth: 24 }} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

// ── Run Header ────────────────────────────────────────────────────────────
const RunHeader = ({ run, runStatus, onAction, onBack }) => {
  const counts = [
    run.rows_total && `${run.rows_total} rows`,
    run.rows_valid && `${run.rows_valid} valid`,
    run.rows_failed && `${run.rows_failed} failed`,
    run.rows_posted && `${run.rows_posted} posted`,
  ].filter(Boolean).join(' · ');

  // Action buttons per state
  const actions = (() => {
    const ghost = (l, ic) => <button className="cs-btn cs-btn-ghost" onClick={() => onAction(ic)}>{l}</button>;
    const pri   = (l, ic, isDanger) => <button className={`cs-btn ${isDanger ? 'cs-btn-danger' : 'cs-btn-primary'}`} onClick={() => onAction(ic)}>{l}</button>;
    switch (runStatus) {
      case 'Draft':      return <>{pri('Parse →', 'parse')}</>;
      case 'Parsed':     return <>{ghost('Re-parse', 'reparse')}{ghost('Discard', 'discard')}{pri('Validate →', 'validate')}</>;
      case 'Validated':  return <>{ghost('Re-validate', 'validate')}{ghost('Discard', 'discard')}{pri('Queue Import →', 'queue')}</>;
      case 'Queued':
      case 'Processing': return <>{pri('Cancel', 'cancel', true)}</>;
      case 'Completed':  return <>{ghost('Download diagnostics', 'download')}{pri('Revert', 'revert', true)}</>;
      case 'Failed':     return <>{ghost('Download diagnostics', 'download')}{ghost('Discard', 'discard')}{pri('Re-validate', 'validate')}</>;
      case 'Cancelled':  return <>{ghost('Discard', 'discard')}{pri('Re-queue', 'queue')}</>;
      case 'Reverting':  return null;
      case 'Reverted':   return <>{ghost('Discard', 'discard')}{pri('Re-queue', 'queue')}</>;
      case 'Revert-Failed': return <>{ghost('Open in Desk', 'desk')}{pri('Retry Revert', 'revert', true)}</>;
      default: return null;
    }
  })();

  return (
    <div style={{ padding: '20px 28px 16px', borderBottom: '1px solid var(--cs-line)', background: 'var(--cs-bg)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button className="cs-btn cs-btn-ghost" style={{ padding: '4px 6px' }} onClick={onBack}><Icon name="arrow-left" size={16}/></button>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0, fontFamily: 'ui-monospace, monospace', letterSpacing: '-0.01em' }}>{run.name}</h1>
        <StatusPill kind="run-status" value={runStatus} size="md"/>
        <div style={{ flex: 1 }} />
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--cs-text-3)' }}>
          <Icon name="dot" size={12} color="#22c55e" />Live
        </span>
        <button className="cs-btn cs-btn-ghost" style={{ padding: '4px 8px' }}><Icon name="external-link" size={14}/> Open in Desk</button>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: 'var(--cs-text-2)', flexWrap: 'wrap' }}>
          <span><b style={{ color: 'var(--cs-text)', fontWeight: 500 }}>{run.company || 'Karachi Trading Co.'}</b></span>
          <span style={{ color: 'var(--cs-line)' }}>·</span>
          <span>{run.period_start ? window.fmtRange(run.period_start, run.period_end) : '— period set on parse —'}</span>
          {counts && <>
            <span style={{ color: 'var(--cs-line)' }}>·</span>
            <span className="cs-num">{counts}</span>
          </>}
        </div>
        {actions && <div style={{ display: 'flex', gap: 8 }}>{actions}</div>}
      </div>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SECTION I — UPLOAD
// ────────────────────────────────────────────────────────────────────────────

const UploadSection = ({ onParse }) => {
  const [file, setFile] = React.useState(null);
  const [adv, setAdv] = React.useState(false);
  const [dragOver, setDragOver] = React.useState(false);
  const [parsing, setParsing] = React.useState(false);

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, maxWidth: 720, margin: '0 auto' }}>
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Company</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: 'var(--cs-surface)', border: '1px solid var(--cs-line)', borderRadius: 10 }}>
          <Icon name="box" size={14} color="var(--cs-text-3)"/>
          <span style={{ fontSize: 13, flex: 1 }}>Karachi Trading Co.</span>
          <Icon name="chevron-down" size={12} color="var(--cs-text-3)"/>
        </div>
      </div>

      {/* Dropzone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) setFile({ name: f.name, size: f.size }); }}
        onClick={() => setFile({ name: 'cashew-export-may-2026.csv', size: 38_492 })}
        style={{
          width: '100%', minHeight: 220, border: `2px dashed ${dragOver ? 'var(--cs-accent)' : 'var(--cs-line)'}`,
          borderRadius: 20, background: dragOver ? 'var(--cs-accent-50)' : 'var(--cs-surface)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 10, padding: 32, cursor: 'pointer', transition: 'border-color .15s, background .15s',
        }}>
        {file ? (
          <div style={{ display:'flex', alignItems:'center', gap:12, background: 'var(--cs-bg-2)', borderRadius: 14, padding: '12px 14px' }}>
            <div style={{ width: 36, height: 36, borderRadius: 12, background: 'var(--cs-accent-50)', color: 'var(--cs-accent-700)', display:'flex', alignItems:'center', justifyContent:'center' }}>
              <Icon name="file" size={18}/>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{file.name}</span>
              <span style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>{(file.size/1024).toFixed(1)} KB · CSV</span>
            </div>
            <button className="cs-btn cs-btn-ghost" style={{ padding: 4 }} onClick={(e) => { e.stopPropagation(); setFile(null); }}>
              <Icon name="x" size={14}/>
            </button>
          </div>
        ) : <>
          <div style={{ width: 56, height: 56, borderRadius: 18, background: 'var(--cs-accent-50)', color: 'var(--cs-accent)', display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Icon name="upload-cloud" size={26}/>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Drop your Cashew CSV here</div>
            <div style={{ fontSize: 13, color: 'var(--cs-text-2)' }}>or click to browse</div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>Accepted: .csv (Cashew app export)</div>
        </>}
      </div>

      {/* Advanced */}
      <div style={{ width: '100%' }}>
        <button onClick={() => setAdv(a => !a)} className="cs-btn cs-btn-ghost" style={{ padding: '4px 6px', fontSize: 12 }}>
          <Icon name={adv ? 'chevron-down' : 'chevron-right'} size={12}/> Advanced
        </button>
        {adv && (
          <div className="cs-card" style={{ padding: 14, marginTop: 8, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Balance Adjustment Account</label>
              <input className="cs-input" placeholder="(default from Cashew Settings)" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>JE Rounding Tolerance</label>
              <input className="cs-input" defaultValue="0.01" style={{ width: 120 }} />
            </div>
          </div>
        )}
      </div>

      {/* Primary actions */}
      <div style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8 }}>
        <a className="cs-link" style={{ fontSize: 13 }}>Cancel</a>
        <button className="cs-btn cs-btn-primary" disabled={!file || parsing}
                onClick={() => { setParsing(true); setTimeout(() => { setParsing(false); onParse?.(); }, 800); }}
                style={{ opacity: !file || parsing ? 0.6 : 1, cursor: !file || parsing ? 'not-allowed' : 'pointer' }}>
          {parsing && <Icon name="loader" size={14} style={{ animation: 'cs-pulse 1s linear infinite' }}/>}
          {parsing ? 'Parsing…' : 'Parse →'}
        </button>
      </div>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SECTION II — PREVIEW
// ────────────────────────────────────────────────────────────────────────────

const StatCell = ({ label, value, sub }) => (
  <div className="cs-card" style={{ padding: 12, minWidth: 0 }}>
    <div style={{ fontSize: 10, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>{label}</div>
    <div style={{ fontSize: 20, fontWeight: 600, marginTop: 4, color: 'var(--cs-text)', letterSpacing: '-0.01em' }} className="cs-num">{value}</div>
    {sub && <div style={{ fontSize: 11, color: 'var(--cs-text-3)', marginTop: 2 }}>{sub}</div>}
  </div>
);

const PreviewSection = () => {
  const rows = window.CASHEW_DATA.ROWS.slice(0, 14);
  const ROWS = window.CASHEW_DATA.ROWS;
  const cnt = (pred) => ROWS.filter(pred).length;
  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
        <StatCell label="Total Rows"  value={ROWS.length} sub="parsed" />
        <StatCell label="Period"      value="May" sub="1 – 24, 2026" />
        <StatCell label="Income"      value={cnt(r => r.txn_type === 'Income')} sub="rows" />
        <StatCell label="Expense"     value={cnt(r => r.txn_type === 'Expense')} sub="rows" />
        <StatCell label="Transfers"   value={cnt(r => r.txn_type.includes('Transfer'))} sub="rows" />
        <StatCell label="Adjustments" value={cnt(r => r.txn_type === 'Adjustment')} sub="rows" />
        <StatCell label="Duplicates"  value={cnt(r => r.is_duplicate)} sub="flagged" />
      </div>

      <div className="cs-card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="eye" size={14} color="var(--cs-text-3)"/>
            <span style={{ fontSize: 13, fontWeight: 500 }}>Preview — {rows.length} of {ROWS.length} rows</span>
          </div>
          <span style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>Read-only · validate to begin editing</span>
        </div>
        <div style={{ maxHeight: 360, overflow: 'auto' }}>
          <table className="cs-table">
            <thead>
              <tr>
                <th style={{ width: 36 }}>#</th>
                <th style={{ width: 80 }}>Date</th>
                <th>Account</th>
                <th style={{ textAlign: 'right', width: 130 }}>Amount</th>
                <th style={{ width: 110 }}>Type</th>
                <th>Category</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.row_idx}>
                  <td className="cs-num" style={{ color: 'var(--cs-text-3)' }}>{r.row_idx}</td>
                  <td>{window.fmtDate(r.txn_date)}</td>
                  <td>{r.raw_account}</td>
                  <td align="right"><AmountDisplay amount={r.base_amount} signed signSource={r.income_flag} /></td>
                  <td><StatusPill kind="txn-type" value={r.txn_type} size="sm" /></td>
                  <td>
                    <div style={{ fontSize: 13 }}>{r.category}</div>
                    {r.sub_category && <div style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>{r.sub_category}</div>}
                  </td>
                  <td style={{ color: 'var(--cs-text-2)', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.sub_category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SECTION III — ROWS WORKBENCH (the big one)
// ────────────────────────────────────────────────────────────────────────────

const ValidationFixModal = ({ row, onClose, onSave }) => {
  const [party, setParty] = React.useState(row.resolved_party || '');
  const [partyType, setPartyType] = React.useState(row.resolved_party_type || 'Supplier');
  const [account, setAccount] = React.useState(row.resolved_account || '');
  if (!row) return null;
  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, background: 'rgba(15,15,15,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 30, padding: 16,
    }}>
      <div className="cs-card" onClick={e => e.stopPropagation()} style={{ width: 580, maxWidth: '100%', maxHeight: '90%', overflow: 'auto', boxShadow: 'var(--cs-shadow-lg)' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--cs-line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 28, height: 28, borderRadius: 999, background: 'var(--cs-red-bg)', color: 'var(--cs-red)', display:'flex', alignItems:'center', justifyContent:'center' }}>
              <Icon name="alert-circle" size={16}/>
            </span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Fix row #{row.row_idx}</div>
              <div style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>{row.validation_error_code}</div>
            </div>
          </div>
          <button className="cs-btn cs-btn-ghost" onClick={onClose} style={{ padding: 4 }}><Icon name="x" size={14}/></button>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ padding: 12, background: '#fef2f2', borderRadius: 12, border: '1px solid #fecaca', fontSize: 13, color: '#991b1b' }}>
            {row.validation_error_message}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, fontSize: 12 }}>
            <div><div style={{ color: 'var(--cs-text-3)' }}>Date</div><div>{window.fmtDate(row.txn_date, 'medium')}</div></div>
            <div><div style={{ color: 'var(--cs-text-3)' }}>Account</div><div>{row.raw_account}</div></div>
            <div><div style={{ color: 'var(--cs-text-3)' }}>Amount</div><div className="cs-num"><AmountDisplay amount={row.base_amount} signed signSource={row.income_flag}/></div></div>
            <div><div style={{ color: 'var(--cs-text-3)' }}>Category</div><div>{row.category}</div></div>
          </div>
          <div style={{ height: 1, background: 'var(--cs-line-2)' }}/>
          {row.validation_error_code === 'NO_ACCOUNT_MAP' && (
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Resolved Account</label>
              <input className="cs-input" value={account} onChange={e => setAccount(e.target.value)} placeholder="Search account…" style={{ marginTop: 4 }}/>
            </div>
          )}
          {row.validation_error_code === 'MISSING_PARTY' && <>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: '0 0 140px' }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Party Type</label>
                <select className="cs-input" value={partyType} onChange={e => setPartyType(e.target.value)} style={{ marginTop: 4 }}>
                  <option>Customer</option><option>Supplier</option>
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Party</label>
                <input className="cs-input" value={party} onChange={e => setParty(e.target.value)} placeholder={`Search ${partyType}…`} style={{ marginTop: 4 }}/>
              </div>
            </div>
          </>}
          {row.validation_error_code === 'NO_EXTERNAL_ACCT' && (
            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Destination Account</label>
              <input className="cs-input" placeholder="Search account…" style={{ marginTop: 4 }}/>
            </div>
          )}
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'space-between' }}>
          <button className="cs-btn cs-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="cs-btn cs-btn-primary" onClick={() => { onSave?.({ row_idx: row.row_idx, party, partyType, account }); onClose(); }}>
            <Icon name="check" size={14}/> Save & re-validate
          </button>
        </div>
      </div>
    </div>
  );
};

const BulkPartyModal = ({ count, onClose, onSave }) => {
  const [type, setType] = React.useState('Customer');
  const [party, setParty] = React.useState('');
  return (
    <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(15,15,15,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 30, padding: 16 }}>
      <div className="cs-card" onClick={e => e.stopPropagation()} style={{ width: 480, maxWidth: '100%', boxShadow: 'var(--cs-shadow-lg)' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Set party for {count} selected rows</div>
          <button className="cs-btn cs-btn-ghost" onClick={onClose} style={{ padding: 4 }}><Icon name="x" size={14}/></button>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Party Type</label>
            <select className="cs-input" value={type} onChange={e => setType(e.target.value)} style={{ marginTop: 4 }}>
              <option>Customer</option><option>Supplier</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--cs-text-2)' }}>Party</label>
            <input className="cs-input" value={party} onChange={e => setParty(e.target.value)} placeholder={`Search ${type}…`} style={{ marginTop: 4 }} autoFocus/>
          </div>
          <div style={{ fontSize: 11, color: 'var(--cs-text-3)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Icon name="info" size={12}/> Existing party values on selected rows will be overwritten.
          </div>
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'space-between' }}>
          <button className="cs-btn cs-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="cs-btn cs-btn-primary" onClick={() => { onSave?.({ type, party }); onClose(); }}>Set party</button>
        </div>
      </div>
    </div>
  );
};

const FILTERS_FACETS = [
  { key: 'validation_status', label: 'Validation', options: ['Valid','Error','Skipped'] },
  { key: 'txn_type',          label: 'Type',       options: ['Income','Expense','Transfer','External Transfer','Adjustment','Loan Receivable','Loan Payable'] },
];

const RowsWorkbench = ({ runStatus, density = 'comfortable', onQueue }) => {
  const ALL = window.CASHEW_DATA.ROWS;
  const isProcessing = runStatus === 'Processing' || runStatus === 'Queued';
  const readonly = isProcessing;

  const [filters, setFilters] = React.useState(() => runStatus === 'Validated' && ALL.some(r => r.validation_status === 'Error') ? { validation_status: ['Error'] } : {});
  const [search, setSearch] = React.useState('');
  const [selected, setSelected] = React.useState(new Set());
  const [editingParty, setEditingParty] = React.useState(null); // row_idx
  const [partyDraft, setPartyDraft] = React.useState({ type: 'Supplier', name: '' });
  const [fixingRow, setFixingRow] = React.useState(null);
  const [showBulkParty, setShowBulkParty] = React.useState(false);
  const [showColumns, setShowColumns] = React.useState(false);
  const [showFilters, setShowFilters] = React.useState(false);
  const [postedRows, setPostedRows] = React.useState(new Set()); // sim

  // For Processing simulation
  React.useEffect(() => {
    if (!isProcessing) return;
    const ids = ALL.filter(r => r.validation_status === 'Valid').map(r => r.row_idx);
    let i = 0;
    setPostedRows(new Set(ids.slice(0, Math.floor(ids.length * 0.5))));
    const t = setInterval(() => {
      i++;
      setPostedRows(new Set(ids.slice(0, Math.min(ids.length, Math.floor(ids.length * 0.5) + i))));
      if (i >= ids.length / 2) clearInterval(t);
    }, 1200);
    return () => clearInterval(t);
  }, [isProcessing]);

  const filtered = ALL.filter(r => {
    for (const k of Object.keys(filters)) {
      if (filters[k]?.length && !filters[k].includes(r[k])) return false;
    }
    if (search) {
      const s = search.toLowerCase();
      if (![r.raw_account, r.category, r.sub_category, r.resolved_account, r.resolved_party].filter(Boolean).some(v => String(v).toLowerCase().includes(s))) return false;
    }
    return true;
  });

  // Top banner
  const errCount = ALL.filter(r => r.validation_status === 'Error').length;
  const validCount = ALL.filter(r => r.validation_status === 'Valid').length;
  let banner = null;
  if (runStatus === 'Validated') {
    if (errCount > 0) banner = { color: 'red', icon: 'alert-circle', text: `${errCount} row${errCount===1?'':'s'} need attention.`, sub: `Fix validation errors before queueing.` };
    else              banner = { color: 'green', icon: 'check-circle', text: `All ${validCount} rows valid. Ready to queue.`, sub: `Click "Queue Import" to post to the General Ledger.` };
  } else if (runStatus === 'Queued') {
    banner = { color: 'indigo', icon: 'clock', text: 'Queued — waiting for worker…', sub: 'You can cancel if you queued by mistake.' };
  } else if (runStatus === 'Processing') {
    banner = { color: 'indigo', icon: 'loader', text: `Posting ${postedRows.size} of ${validCount}…`, sub: 'Rows update live as the worker processes them.', progress: validCount ? (postedRows.size / validCount) : 0 };
  }

  const toggleFilter = (key, val) => {
    setFilters(f => {
      const cur = f[key] || [];
      const next = cur.includes(val) ? cur.filter(v => v !== val) : [...cur, val];
      return { ...f, [key]: next };
    });
  };

  const toggleSel = (idx) => {
    setSelected(s => { const n = new Set(s); n.has(idx) ? n.delete(idx) : n.add(idx); return n; });
  };
  const toggleAllSel = () => {
    setSelected(s => s.size === filtered.length ? new Set() : new Set(filtered.map(r => r.row_idx)));
  };

  const rowHeight = density === 'compact' ? 30 : 40;
  const rowPadding = density === 'compact' ? '4px 10px' : '8px 10px';

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14, position: 'relative' }}>
      {banner && (
        <div className="cs-card" style={{
          padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10,
          borderLeft: `3px solid ${banner.color === 'red' ? 'var(--cs-red)' : banner.color === 'green' ? 'var(--cs-green)' : 'var(--cs-accent)'}`,
        }}>
          <span style={{
            width: 28, height: 28, borderRadius: 999,
            background: banner.color === 'red' ? 'var(--cs-red-bg)' : banner.color === 'green' ? 'var(--cs-green-bg)' : 'var(--cs-indigo-bg)',
            color: banner.color === 'red' ? 'var(--cs-red)' : banner.color === 'green' ? 'var(--cs-green)' : 'var(--cs-indigo-fg)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }} className={banner.icon === 'loader' ? 'cs-pulse' : ''}>
            <Icon name={banner.icon} size={15}/>
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{banner.text}</div>
            <div style={{ fontSize: 12, color: 'var(--cs-text-2)' }}>{banner.sub}</div>
          </div>
          {banner.progress != null && (
            <div style={{ width: 200 }}>
              <MiniBar value={banner.progress * 100} max={100} color="var(--cs-accent)" height={6}/>
              <div style={{ fontSize: 11, color: 'var(--cs-text-3)', marginTop: 4, textAlign: 'right' }}>{Math.round(banner.progress * 100)}%</div>
            </div>
          )}
          {runStatus === 'Validated' && errCount === 0 && (
            <button className="cs-btn cs-btn-primary" onClick={onQueue}>Queue Import →</button>
          )}
        </div>
      )}

      {/* Toolbar */}
      {!readonly && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: '0 1 320px', minWidth: 200 }}>
            <Icon name="search" size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--cs-text-3)' }}/>
            <input className="cs-input" placeholder="Search rows…" value={search} onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 30 }}/>
          </div>
          <div style={{ position: 'relative' }}>
            <button className={`cs-chip ${Object.values(filters).some(v => v?.length) ? 'cs-chip-active' : ''}`} onClick={() => setShowFilters(s => !s)}>
              <Icon name="filter" size={13}/> Filters
              {Object.values(filters).flatMap(v => v || []).length > 0 && <span style={{ background: 'var(--cs-accent)', color: '#fff', borderRadius: 999, padding: '0 6px', fontSize: 10, fontWeight: 600 }}>{Object.values(filters).flatMap(v => v || []).length}</span>}
            </button>
            {showFilters && (
              <div className="cs-card" style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 20, padding: 12, minWidth: 240, boxShadow: 'var(--cs-shadow-lg)' }} onMouseLeave={() => setShowFilters(false)}>
                {FILTERS_FACETS.map(f => (
                  <div key={f.key} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 11, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600, marginBottom: 6 }}>{f.label}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {f.options.map(opt => {
                        const active = (filters[f.key] || []).includes(opt);
                        return (
                          <button key={opt} className={`cs-chip ${active ? 'cs-chip-active' : ''}`} style={{ padding: '3px 8px', fontSize: 11 }} onClick={() => toggleFilter(f.key, opt)}>
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button className="cs-chip" onClick={() => setShowColumns(true)}><Icon name="columns" size={13}/> Columns</button>
          <div style={{ flex: 1 }}/>
          <button className="cs-btn"><Icon name="refresh" size={13}/> Re-validate all</button>
        </div>
      )}

      {/* Active filter chips */}
      {Object.entries(filters).flatMap(([k, vals]) => (vals || []).map(v => [k, v])).length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {Object.entries(filters).flatMap(([k, vals]) => (vals || []).map(v => (
            <span key={`${k}:${v}`} style={{ display:'inline-flex', alignItems:'center', gap: 4, padding: '3px 4px 3px 8px', background: 'var(--cs-accent-50)', color: 'var(--cs-accent-700)', borderRadius: 6, fontSize: 12 }}>
              {FILTERS_FACETS.find(f => f.key === k)?.label}: {v}
              <button onClick={() => toggleFilter(k, v)} style={{ border:0, background:'transparent', padding: 2, cursor: 'pointer', display:'flex', color:'var(--cs-accent-700)' }}>
                <Icon name="x" size={11}/>
              </button>
            </span>
          )))}
          <button className="cs-link" style={{ background:'none', border:0, padding:0, fontSize: 12, cursor: 'pointer' }} onClick={() => setFilters({})}>Clear all</button>
        </div>
      )}

      {/* Table */}
      <div className="cs-card" style={{ overflow: 'hidden' }}>
        <div style={{ overflow: 'auto', maxHeight: 540 }}>
          <table className="cs-table">
            <thead>
              <tr>
                {!readonly && <th style={{ width: 32 }}>
                  <input type="checkbox" checked={selected.size > 0 && selected.size === filtered.length} onChange={toggleAllSel}/>
                </th>}
                <th style={{ width: 36 }}>#</th>
                <th style={{ width: 90 }}>Status</th>
                <th style={{ width: 80 }}>Date</th>
                <th>Account</th>
                <th style={{ textAlign: 'right', width: 130 }}>Amount</th>
                <th style={{ width: 110 }}>Type</th>
                <th>Category</th>
                <th>Party</th>
                {isProcessing && <th style={{ width: 130 }}>Posted As</th>}
                {!readonly && <th>Error / Resolved Account</th>}
                <th style={{ width: 36 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => {
                const isErr = r.validation_status === 'Error';
                const isSel = selected.has(r.row_idx);
                const isPosted = postedRows.has(r.row_idx);
                const isDup = r.is_duplicate;
                const editing = editingParty === r.row_idx;
                return (
                  <tr key={r.row_idx} style={{
                    borderLeft: isErr ? '3px solid var(--cs-red)' : isPosted ? '3px solid var(--cs-green)' : '3px solid transparent',
                    background: isSel ? 'var(--cs-accent-50)' : isDup ? 'rgba(0,0,0,0.015)' : undefined,
                    opacity: r.validation_status === 'Skipped' ? 0.6 : 1,
                    height: rowHeight,
                  }}>
                    {!readonly && <td style={{ padding: rowPadding }}><input type="checkbox" checked={isSel} onChange={() => toggleSel(r.row_idx)}/></td>}
                    <td style={{ padding: rowPadding }} className="cs-num">{r.row_idx}</td>
                    <td style={{ padding: rowPadding }}><StatusPill kind="row-validation" value={r.validation_status} size="sm"/></td>
                    <td style={{ padding: rowPadding }}>{window.fmtDate(r.txn_date)}</td>
                    <td style={{ padding: rowPadding }}>{r.raw_account}</td>
                    <td align="right" style={{ padding: rowPadding }}><AmountDisplay amount={r.base_amount} signed signSource={r.income_flag}/></td>
                    <td style={{ padding: rowPadding }}><StatusPill kind="txn-type" value={r.txn_type} size="sm"/></td>
                    <td style={{ padding: rowPadding }}>
                      <div style={{ fontSize: 13 }}>{r.category}</div>
                      {r.sub_category && density !== 'compact' && <div style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>{r.sub_category}</div>}
                    </td>
                    <td style={{ padding: rowPadding, minWidth: 160 }} onDoubleClick={() => !readonly && setEditingParty(r.row_idx)}>
                      {editing ? (
                        <div style={{ display: 'flex', gap: 4 }}>
                          <select className="cs-input" style={{ padding: '3px 6px', fontSize: 12, width: 90 }} value={partyDraft.type} onChange={e => setPartyDraft(p => ({ ...p, type: e.target.value }))}>
                            <option>Customer</option><option>Supplier</option>
                          </select>
                          <input className="cs-input" style={{ padding: '3px 6px', fontSize: 12, flex: 1 }} autoFocus placeholder="Search…"
                                 value={partyDraft.name} onChange={e => setPartyDraft(p => ({ ...p, name: e.target.value }))}
                                 onKeyDown={e => { if (e.key === 'Enter') setEditingParty(null); if (e.key === 'Escape') setEditingParty(null); }}/>
                          <button className="cs-btn cs-btn-ghost" style={{ padding: 4 }} onClick={() => setEditingParty(null)}><Icon name="check" size={12}/></button>
                        </div>
                      ) : r.resolved_party ? (
                        <span style={{ fontSize: 12 }}><span style={{ fontSize: 10, color: 'var(--cs-text-3)' }}>{r.resolved_party_type}: </span>{r.resolved_party}</span>
                      ) : (
                        <span style={{ fontSize: 11, color: 'var(--cs-text-3)', fontStyle: 'italic' }}>{readonly ? '—' : 'double-click to set'}</span>
                      )}
                    </td>
                    {isProcessing && (
                      <td style={{ padding: rowPadding, fontSize: 12 }}>
                        {isPosted
                          ? <span style={{ color: 'var(--cs-green)', display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="check" size={12}/> JE-25-{String(r.row_idx).padStart(4, '0')}</span>
                          : <span style={{ color: 'var(--cs-text-3)' }}>—</span>}
                      </td>
                    )}
                    {!readonly && (
                      <td style={{ padding: rowPadding, fontSize: 12, color: isErr ? 'var(--cs-red)' : 'var(--cs-text-3)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title={r.validation_error_message}>
                        {isErr ? r.validation_error_message : r.resolved_account || '—'}
                      </td>
                    )}
                    <td style={{ padding: rowPadding }}>
                      {!readonly && (
                        <div className="cs-row-hover-actions">
                          <KebabMenu items={[
                            isErr && { label: 'Fix this row…', icon: 'edit-2', action: () => setFixingRow(r) },
                            { label: 'Re-validate', icon: 'refresh' },
                            { label: 'View row JSON', icon: 'file' },
                          ].filter(Boolean)}/>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={11} style={{ padding: 32, textAlign: 'center', color: 'var(--cs-text-3)' }}>No rows match current filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selection footer */}
      {!readonly && selected.size > 0 && (
        <div style={{
          position: 'sticky', bottom: 12, alignSelf: 'center',
          background: 'var(--cs-text)', color: '#fff', padding: '8px 12px', borderRadius: 999,
          boxShadow: 'var(--cs-shadow-lg)', display: 'flex', alignItems: 'center', gap: 10,
          fontSize: 13, zIndex: 5,
        }}>
          <span style={{ fontWeight: 500 }}>{selected.size} row{selected.size === 1 ? '' : 's'} selected</span>
          <span style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.15)' }} />
          <button className="cs-btn cs-btn-sm" onClick={() => setShowBulkParty(true)} style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', border: 0 }}>
            <Icon name="users" size={12}/> Set party…
          </button>
          <button className="cs-btn cs-btn-sm" style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', border: 0 }}>
            <Icon name="refresh" size={12}/> Re-validate
          </button>
          <button onClick={() => setSelected(new Set())} style={{ background: 'transparent', border: 0, color: 'rgba(255,255,255,0.7)', cursor: 'pointer', fontSize: 12 }}>
            Clear
          </button>
        </div>
      )}

      {fixingRow && <ValidationFixModal row={fixingRow} onClose={() => setFixingRow(null)} onSave={() => {}} />}
      {showBulkParty && <BulkPartyModal count={selected.size} onClose={() => setShowBulkParty(false)} onSave={() => setSelected(new Set())} />}
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SECTION IV — COMPLETED SUMMARY
// ────────────────────────────────────────────────────────────────────────────

const CompletedSummary = ({ runStatus, run, onAction }) => {
  const ALL = window.CASHEW_DATA.ROWS;
  const reverted = runStatus === 'Reverted' || runStatus === 'Reverting';
  const failed = runStatus === 'Failed' || runStatus === 'Revert-Failed';

  const banner = (() => {
    if (runStatus === 'Completed') return { icon: 'check-circle', color: 'green', title: `Completed — ${run.rows_posted} rows posted`, sub: run.rows_failed ? `${run.rows_failed} rows failed validation` : 'All valid rows posted to the General Ledger.' };
    if (runStatus === 'Failed')    return { icon: 'x-circle', color: 'red', title: 'Import failed', sub: 'Worker hit an unrecoverable error. Download diagnostics for details.' };
    if (runStatus === 'Cancelled') return { icon: 'x', color: 'gray', title: 'Cancelled', sub: 'Cancelled by operator before posting completed.' };
    if (runStatus === 'Reverting') return { icon: 'loader', color: 'amber', title: 'Reverting…', sub: 'Reversing posted documents. Do not close this tab.', pulse: true };
    if (runStatus === 'Reverted')  return { icon: 'rotate-ccw', color: 'amber', title: 'Reverted', sub: 'All posted documents have been reversed. Source CSV remains attached.' };
    if (runStatus === 'Revert-Failed') return { icon: 'alert-circle', color: 'red', title: 'Revert failed', sub: 'Some posted documents could not be reversed. Open in Desk for manual cleanup.' };
  })();

  const breakdown = [
    { dt: 'Journal Entry', count: 88 },
    { dt: 'Sales Invoice', count: 14 },
    { dt: 'Purchase Invoice', count: 8 },
    { dt: 'Transfer JV', count: 8 },
    { dt: 'External Transfer JE', count: 4 },
    { dt: 'Adjustment JE', count: 2 },
    { dt: 'Failed/Skipped', count: 2 },
  ];
  const maxC = Math.max(...breakdown.map(b => b.count));

  return (
    <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Result banner */}
      <div className="cs-card" style={{
        padding: 18, display: 'flex', alignItems: 'flex-start', gap: 14,
        borderLeft: `4px solid ${banner.color === 'green' ? 'var(--cs-green)' : banner.color === 'red' ? 'var(--cs-red)' : banner.color === 'amber' ? 'var(--cs-amber)' : 'var(--cs-line)'}`,
      }}>
        <span className={banner.pulse ? 'cs-pulse' : ''} style={{
          width: 44, height: 44, borderRadius: 999,
          background: banner.color === 'green' ? 'var(--cs-green-bg)' : banner.color === 'red' ? 'var(--cs-red-bg)' : banner.color === 'amber' ? 'var(--cs-amber-bg)' : 'var(--cs-bg-2)',
          color: banner.color === 'green' ? '#15803d' : banner.color === 'red' ? 'var(--cs-red)' : banner.color === 'amber' ? '#92400e' : 'var(--cs-text-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}><Icon name={banner.icon} size={22}/></span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>{banner.title}</div>
          <div style={{ fontSize: 13, color: 'var(--cs-text-2)' }}>{banner.sub}</div>
          <div style={{ fontSize: 12, color: 'var(--cs-text-3)', marginTop: 8 }}>Started 2h ago · Finished 1h ago</div>
        </div>
      </div>

      {/* Counts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
        <StatCell label="Total"   value={run.rows_total} sub="rows imported" />
        <StatCell label="Valid"   value={run.rows_valid} sub="passed validation" />
        <StatCell label="Posted"  value={reverted ? 0 : run.rows_posted} sub={reverted ? 'reverted' : 'in GL'} />
        <StatCell label="Failed"  value={run.rows_failed} sub="errors" />
        <StatCell label="Skipped" value={run.rows_skipped} sub="ignored" />
      </div>

      {/* Posted breakdown */}
      <div className="cs-card" style={{ padding: 18 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Posted by document type</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {breakdown.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ flex: '0 0 180px', fontSize: 13 }}>{b.dt}</div>
              <div style={{ flex: 1 }}><MiniBar value={b.count} max={maxC} color={b.dt === 'Failed/Skipped' ? 'var(--cs-red)' : 'var(--cs-accent)'}/></div>
              <div style={{ flex: '0 0 50px', textAlign: 'right', fontSize: 13, fontWeight: 500 }} className="cs-num">{b.count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Read-only rows preview */}
      <div className="cs-card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Posted rows · {ALL.filter(r => r.validation_status === 'Valid').length}</div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="cs-chip cs-chip-active" style={{ padding: '3px 8px', fontSize: 11 }}>Posted</button>
            <button className="cs-chip" style={{ padding: '3px 8px', fontSize: 11 }}>Show all</button>
          </div>
        </div>
        <div style={{ maxHeight: 280, overflow: 'auto' }}>
          <table className="cs-table">
            <thead>
              <tr>
                <th style={{ width: 36 }}>#</th>
                <th style={{ width: 80 }}>Date</th>
                <th>Account</th>
                <th style={{ textAlign: 'right', width: 130 }}>Amount</th>
                <th>Posted as</th>
              </tr>
            </thead>
            <tbody>
              {ALL.filter(r => r.validation_status === 'Valid').slice(0, 8).map(r => (
                <tr key={r.row_idx}>
                  <td className="cs-num" style={{ color: 'var(--cs-text-3)' }}>{r.row_idx}</td>
                  <td>{window.fmtDate(r.txn_date)}</td>
                  <td>{r.raw_account}</td>
                  <td align="right"><AmountDisplay amount={r.base_amount} signed signSource={r.income_flag}/></td>
                  <td style={{ fontSize: 12 }}>
                    {reverted
                      ? <span style={{ color: 'var(--cs-amber)' }}><Icon name="rotate-ccw" size={11} style={{ verticalAlign: 'middle' }}/> Reverted</span>
                      : <span><span style={{ color: 'var(--cs-text-3)' }}>JE </span><a className="cs-link">JE-25-{String(r.row_idx).padStart(4, '0')}</a></span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Danger zone */}
      {runStatus === 'Completed' && (
        <div className="cs-card" style={{ padding: 18, borderColor: '#fecaca', background: '#fef2f2' }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#991b1b' }}>Danger zone</h3>
          <div style={{ fontSize: 13, color: '#991b1b', marginTop: 4, marginBottom: 12 }}>This will reverse every posted document. The original CSV file will remain attached.</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="cs-btn cs-btn-danger" onClick={() => onAction?.('revert')}><Icon name="rotate-ccw" size={13}/> Revert this import</button>
            <button className="cs-btn"><Icon name="download" size={13}/> Download diagnostics CSV</button>
          </div>
        </div>
      )}
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// COMPOSER
// ────────────────────────────────────────────────────────────────────────────

const RunWorkspace = ({ initialStatus = 'Validated', density = 'comfortable', onBack }) => {
  const [status, setStatus] = React.useState(initialStatus);
  const [confirm, setConfirm] = React.useState(null);
  const run = {
    name: 'CSH-IMP-2026-000016',
    company: 'Karachi Trading Co.',
    period_start: '2026-05-01',
    period_end: '2026-05-24',
    rows_total: 36, rows_valid: 31, rows_failed: 4, rows_posted: status === 'Completed' || status === 'Reverted' ? 31 : (status === 'Processing' ? 18 : 0), rows_skipped: 1,
  };
  const draftRun = { name: '(new import)' };

  const handleAction = (act) => {
    if (act === 'parse')    setStatus('Parsed');
    if (act === 'validate') setStatus('Validated');
    if (act === 'queue')    { setConfirm({ kind: 'warning', title: 'Queue this import?', body: `Post ${run.rows_valid} valid rows to the General Ledger?`, confirmLabel: 'Queue Import', onConfirm: () => { setStatus('Processing'); setConfirm(null); setTimeout(() => setStatus('Completed'), 6000); } }); return; }
    if (act === 'cancel')   setStatus('Cancelled');
    if (act === 'revert')   { setConfirm({ kind: 'danger', title: 'Revert this import?', body: 'This will reverse all posted JEs. Continue?', confirmLabel: 'Revert', onConfirm: () => { setStatus('Reverting'); setConfirm(null); setTimeout(() => setStatus('Reverted'), 2500); } }); return; }
    if (act === 'discard')  setStatus('Draft');
  };

  const isDraft = status === 'Draft';

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <RunHeader run={isDraft ? draftRun : run} runStatus={status} onAction={handleAction} onBack={onBack}/>
      <StateStepper runStatus={status}/>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {status === 'Draft'     && <UploadSection onParse={() => setStatus('Parsed')}/>}
        {status === 'Parsed'    && <PreviewSection/>}
        {['Validated','Queued','Processing'].includes(status) && <RowsWorkbench runStatus={status} density={density} onQueue={() => handleAction('queue')}/>}
        {['Completed','Failed','Cancelled','Reverting','Reverted','Revert-Failed'].includes(status) && <CompletedSummary runStatus={status} run={run} onAction={handleAction}/>}
      </div>
      {confirm && <ConfirmModal {...confirm} onCancel={() => setConfirm(null)} />}
    </div>
  );
};

const ConfirmModal = ({ kind = 'warning', title, body, confirmLabel = 'Confirm', cancelLabel = 'Cancel', onConfirm, onCancel }) => (
  <div onClick={onCancel} style={{ position: 'absolute', inset: 0, background: 'rgba(15,15,15,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 40, padding: 16 }}>
    <div className="cs-card" onClick={e => e.stopPropagation()} style={{ width: 440, maxWidth: '100%', boxShadow: 'var(--cs-shadow-lg)' }}>
      <div style={{ padding: 20, display: 'flex', gap: 14 }}>
        <span style={{ width: 40, height: 40, borderRadius: 999, background: kind === 'danger' ? 'var(--cs-red-bg)' : 'var(--cs-amber-bg)', color: kind === 'danger' ? 'var(--cs-red)' : '#92400e', display:'flex', alignItems:'center', justifyContent:'center', flexShrink: 0 }}>
          <Icon name="alert-triangle" size={18}/>
        </span>
        <div>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</h3>
          <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--cs-text-2)' }}>{body}</p>
        </div>
      </div>
      <div style={{ padding: '12px 20px', borderTop: '1px solid var(--cs-line)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="cs-btn cs-btn-ghost" onClick={onCancel}>{cancelLabel}</button>
        <button className={`cs-btn ${kind === 'danger' ? 'cs-btn-danger' : 'cs-btn-primary'}`} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </div>
  </div>
);

Object.assign(window, { RunWorkspace, UploadSection, PreviewSection, RowsWorkbench, CompletedSummary, RunHeader, StateStepper, ConfirmModal });
