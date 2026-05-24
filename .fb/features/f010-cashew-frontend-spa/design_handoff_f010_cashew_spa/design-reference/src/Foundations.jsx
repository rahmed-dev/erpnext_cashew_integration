// Foundations artboard — the design system at a glance.

const { Icon, StatusPill, AmountDisplay, Tile, Skel, CashewMark } = window;

const Swatch = ({ label, color, fg = '#fff', desc }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    <div style={{ height: 64, background: color, borderRadius: 14, color: fg, padding: 10, fontSize: 11, fontWeight: 500, display: 'flex', alignItems: 'flex-end' }}>{color}</div>
    <div style={{ fontSize: 12, fontWeight: 500 }}>{label}</div>
    {desc && <div style={{ fontSize: 11, color: 'var(--cs-text-3)' }}>{desc}</div>}
  </div>
);

const Foundations = () => {
  return (
    <div className="cs-root" style={{ padding: 28, background: 'var(--cs-bg)', display: 'flex', flexDirection: 'column', gap: 28, height: '100%', overflow: 'auto' }}>
      {/* Brand */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Brand</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: 18, background: 'var(--cs-accent)', color: '#fff', display:'flex', alignItems:'center', justifyContent:'center' }}>
            <CashewMark size={32}/>
          </div>
          <div>
            <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em' }}>Cashew</div>
            <div style={{ fontSize: 13, color: 'var(--cs-text-2)' }}>Personal finance imported into the books.</div>
          </div>
        </div>
      </section>

      {/* Color */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Color</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12 }}>
          <Swatch label="Accent" color="#4f46e5" desc="Cashew brand · primary CTAs"/>
          <Swatch label="Accent-700" color="#4338ca" desc="Hover · active"/>
          <Swatch label="Accent-50" color="#eef2ff" fg="#4338ca" desc="Subtle fills · chips"/>
          <Swatch label="Surface" color="#ffffff" fg="#1c1917" desc="Card backgrounds"/>
          <Swatch label="Background" color="#fbfaf7" fg="#1c1917" desc="App background"/>
          <Swatch label="Sidebar" color="#1c1c1c" desc="Sidebar chrome"/>
          <Swatch label="Success" color="#16a34a" desc="Income · valid · posted"/>
          <Swatch label="Danger" color="#dc2626" desc="Expense · errors · failed"/>
          <Swatch label="Warn" color="#d97706" desc="Reverted · cancelled"/>
          <Swatch label="Info" color="#4f46e5" desc="Queued · processing"/>
        </div>
      </section>

      {/* Type */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Typography</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', marginRight: 12 }}>H1 · 24/600</span>
            <span style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em' }}>Finance Dashboard</span>
          </div>
          <div>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', marginRight: 12 }}>Section · 14/600</span>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Top categories</span>
          </div>
          <div>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', marginRight: 12 }}>Body · 13/400</span>
            <span style={{ fontSize: 13 }}>All Cashew rows post to the General Ledger when you queue a run.</span>
          </div>
          <div>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', marginRight: 12 }}>Caption · 11/500 uppercase</span>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>CASH &amp; BANK</span>
          </div>
          <div>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', marginRight: 12 }}>Numeric · tabular</span>
            <span className="cs-num" style={{ fontSize: 24, fontWeight: 600 }}>Rs 12,485,000.00</span>
          </div>
          <div>
            <span style={{ fontSize: 11, color: 'var(--cs-text-3)', marginRight: 12 }}>Mono · run ids</span>
            <span style={{ fontFamily: 'ui-monospace, monospace', fontSize: 13 }}>CSH-IMP-2026-000017</span>
          </div>
        </div>
        <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 12, background: 'var(--cs-bg-2)', fontSize: 12, color: 'var(--cs-text-2)' }}>
          <b>System UI stack</b> · -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif. Mono = ui-monospace. No webfonts.
        </div>
      </section>

      {/* Status pills */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Status pills</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--cs-text-3)', marginBottom: 6 }}>Run status</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.keys(window.STATUS_MAP['run-status']).map(s => <StatusPill key={s} kind="run-status" value={s}/>)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--cs-text-3)', marginBottom: 6 }}>Row validation</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.keys(window.STATUS_MAP['row-validation']).map(s => <StatusPill key={s} kind="row-validation" value={s}/>)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--cs-text-3)', marginBottom: 6 }}>Transaction type</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.keys(window.STATUS_MAP['txn-type']).map(s => <StatusPill key={s} kind="txn-type" value={s}/>)}
            </div>
          </div>
        </div>
      </section>

      {/* Buttons */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Buttons & chips</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          <button className="cs-btn cs-btn-primary"><Icon name="plus" size={14}/> Primary</button>
          <button className="cs-btn">Secondary</button>
          <button className="cs-btn cs-btn-danger"><Icon name="rotate-ccw" size={13}/> Danger</button>
          <button className="cs-btn cs-btn-ghost">Ghost</button>
          <span className="cs-chip">Chip</span>
          <span className="cs-chip cs-chip-active">Active chip</span>
        </div>
      </section>

      {/* Inputs */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Inputs</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', maxWidth: 600 }}>
          <input className="cs-input" placeholder="Search runs…"/>
          <select className="cs-input" style={{ flex: '0 0 140px' }}><option>Supplier</option><option>Customer</option></select>
        </div>
      </section>

      {/* Tile preview */}
      <section>
        <h2 style={{ fontSize: 13, color: 'var(--cs-text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 12 }}>Tile</h2>
        <div style={{ maxWidth: 280 }}>
          <Tile icon="wallet" label="Cash & Bank" amount={12_485_000} prior={11_180_000} accent="#0891b2"/>
        </div>
      </section>
    </div>
  );
};

Object.assign(window, { Foundations });
