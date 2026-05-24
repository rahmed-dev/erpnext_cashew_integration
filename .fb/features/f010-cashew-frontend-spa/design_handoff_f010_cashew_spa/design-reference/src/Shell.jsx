// Cashew SPA — App Shell. Sidebar + content slot.
// Each artboard's content is mounted here so the app-frame looks identical
// across the canvas.

const { Icon } = window;

const SidebarLink = ({ icon, label, active, collapsed, onClick, badge }) => (
  <a onClick={onClick} style={{
    display: 'flex', alignItems: 'center', gap: 10, padding: collapsed ? '9px' : '8px 10px',
    borderRadius: 10, fontSize: 13, fontWeight: 500,
    color: active ? '#fafafa' : 'var(--cs-sidebar-fg)',
    background: active ? 'var(--cs-sidebar-active)' : 'transparent',
    cursor: 'pointer', position: 'relative',
    transition: 'background .12s, color .12s',
    justifyContent: collapsed ? 'center' : 'flex-start',
  }}
  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--cs-sidebar-hover)'; }}
  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}
  >
    {active && <span style={{ position: 'absolute', left: -8, top: 8, bottom: 8, width: 2, background: 'var(--cs-accent)', borderRadius: 2 }} />}
    <Icon name={icon} size={17} color={active ? '#fafafa' : 'currentColor'} />
    {!collapsed && <span style={{ flex: 1 }}>{label}</span>}
    {!collapsed && badge != null && (
      <span style={{ fontSize: 11, padding: '1px 6px', borderRadius: 999, background: 'var(--cs-accent)', color: '#fff' }}>{badge}</span>
    )}
  </a>
);

const RealtimeDot = ({ state = 'connected' }) => {
  const c = state === 'connected' ? '#22c55e'
          : state === 'reconnecting' ? '#f59e0b'
          : state === 'polling' ? '#a1a1aa'
          : '#ef4444';
  const lbl = state === 'connected' ? 'Live'
            : state === 'reconnecting' ? 'Reconnecting…'
            : state === 'polling' ? 'Polling'
            : 'Offline';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--cs-sidebar-fg-dim)' }}>
      <span style={{
        width: 7, height: 7, borderRadius: 999, background: c,
        boxShadow: state === 'connected' ? `0 0 0 3px ${c}33` : 'none',
        animation: (state === 'reconnecting' || state === 'connected') ? 'cs-pulse 1.4s ease-in-out infinite' : 'none',
      }} />
      {lbl}
    </div>
  );
};

const CashewMark = ({ size = 22 }) => (
  // Stylised "cashew curve" mark — a fat C-arc. Not a real cashew, just abstract glyph.
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M19 8.5c0-2-2-4-5-4-4.5 0-8 3.5-8 8 0 4 3 7.5 7 7.5 2.5 0 4.5-1.5 5-3.5"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    <circle cx="17.5" cy="7" r="1.3" fill="currentColor" />
  </svg>
);

const AppSwitcher = ({ collapsed, onSwitch }) => {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 10, width: '100%',
        padding: collapsed ? '8px' : '8px 10px', borderRadius: 12,
        background: open ? 'var(--cs-sidebar-hover)' : 'transparent',
        color: '#fafafa', border: 0, cursor: 'pointer', textAlign: 'left',
      }}>
        <span style={{
          width: 28, height: 28, borderRadius: 10,
          background: 'var(--cs-accent)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <CashewMark size={18} />
        </span>
        {!collapsed && <>
          <span style={{ flex: 1, fontWeight: 600, fontSize: 14 }}>Cashew</span>
          <Icon name="chevron-down" size={14} color="var(--cs-sidebar-fg)" />
        </>}
      </button>
      {open && !collapsed && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 10,
          background: '#2a2a2a', borderRadius: 12, boxShadow: '0 12px 32px rgba(0,0,0,.4)',
          padding: 4,
        }} onMouseLeave={() => setOpen(false)}>
          {[
            { label: 'Cashew', sub: 'Current', icon: <CashewMark size={14}/>, active: true },
            { label: 'Back to Desk', sub: '/app', icon: <Icon name="arrow-left" size={14}/>, onClick: () => onSwitch?.('desk') },
          ].map((it, i) => (
            <button key={i} onClick={it.onClick} style={{
              display: 'flex', alignItems: 'center', gap: 10, width: '100%',
              padding: '8px 10px', borderRadius: 8, border: 0,
              background: it.active ? '#3a3a3a' : 'transparent',
              color: '#fafafa', fontSize: 13, cursor: 'pointer', textAlign: 'left',
            }}>
              <span style={{ display:'flex', width:18, height:18, alignItems:'center', justifyContent:'center', color: 'var(--cs-sidebar-fg-dim)' }}>{it.icon}</span>
              <span style={{ flex: 1 }}>{it.label}</span>
              <span style={{ fontSize: 11, color: 'var(--cs-sidebar-fg-dim)' }}>{it.sub}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// Active path is determined externally by `route`. onNavigate({to}) lets each
// artboard intercept and swap content within its own state.
const Shell = ({ route = '/', onNavigate, collapsed = false, children, realtimeState = 'connected', user = 'Ali Rahman' }) => {
  const SIDEBAR_W = collapsed ? 60 : 224;
  return (
    <div className="cs-root" style={{ display: 'flex', height: '100%', minHeight: 0, background: 'var(--cs-bg)' }}>
      <aside style={{
        width: SIDEBAR_W, flexShrink: 0,
        background: 'var(--cs-sidebar-bg)', color: 'var(--cs-sidebar-fg)',
        display: 'flex', flexDirection: 'column',
        padding: collapsed ? '12px 6px' : '12px 12px',
        gap: 14, transition: 'width .18s ease',
      }}>
        <AppSwitcher collapsed={collapsed} />
        <div style={{ height: 1, background: '#2a2a2a' }} />
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <SidebarLink icon="bar-chart-2" label="Dashboard" active={route === '/'} collapsed={collapsed} onClick={() => onNavigate?.('/')} />
          <SidebarLink icon="file-text"   label="Imports"   active={route.startsWith('/runs')} collapsed={collapsed} onClick={() => onNavigate?.('/runs')} badge={collapsed ? null : 1} />
        </nav>

        <div style={{ flex: 1 }} />

        <div style={{ height: 1, background: '#2a2a2a' }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {!collapsed ? (
            <button style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
              borderRadius: 10, border: 0, background: 'transparent', cursor: 'pointer',
              color: 'var(--cs-sidebar-fg)', textAlign: 'left',
            }}>
              <div style={{ width: 26, height: 26, borderRadius: 999, background: 'var(--cs-accent)', color: '#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 11, fontWeight: 600 }}>
                {user.split(' ').map(s=>s[0]).slice(0,2).join('')}
              </div>
              <span style={{ flex: 1, fontSize: 12, color: '#fafafa', fontWeight: 500 }}>{user}</span>
              <Icon name="chevron-up" size={12} color="var(--cs-sidebar-fg-dim)" />
            </button>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <div style={{ width: 26, height: 26, borderRadius: 999, background: 'var(--cs-accent)', color: '#fff', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 11, fontWeight: 600 }}>
                {user.split(' ').map(s=>s[0]).slice(0,2).join('')}
              </div>
            </div>
          )}
          {!collapsed && <RealtimeDot state={realtimeState} />}
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0, overflow: 'auto', background: 'var(--cs-bg)' }}>
        {children}
      </main>
    </div>
  );
};

// PageHeader — used on every page top.
const PageHeader = ({ title, subtitle, backRoute, onBack, meta, actions, noBorder }) => (
  <div style={{
    padding: '20px 28px',
    borderBottom: noBorder ? 'none' : '1px solid var(--cs-line)',
    display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap',
    background: 'var(--cs-bg)',
  }}>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {backRoute && (
          <button onClick={onBack} className="cs-btn cs-btn-ghost" style={{ padding: '4px 6px' }}>
            <Icon name="arrow-left" size={16}/>
          </button>
        )}
        <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em', margin: 0, color: 'var(--cs-text)' }}>{title}</h1>
        {meta}
      </div>
      {subtitle && <div style={{ fontSize: 13, color: 'var(--cs-text-2)', marginTop: 4 }}>{subtitle}</div>}
    </div>
    {actions && <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>{actions}</div>}
  </div>
);

Object.assign(window, { Shell, PageHeader, RealtimeDot, CashewMark });
