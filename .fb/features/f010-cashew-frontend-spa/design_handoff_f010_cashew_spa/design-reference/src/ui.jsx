// Cashew SPA — shared primitives & icon set.
// Tailwind classes won't run here (no build step) — everything is inline CSS via objects,
// plus a single injected <style> tag for hover/focus rules.

// ── Theme tokens (CSS vars set on artboard root) ─────────────────────────
// Read from `getComputedStyle(root).getPropertyValue('--cs-accent')` if needed.

const css = `
.cs-root {
  --cs-accent: #4f46e5;
  --cs-accent-50: #eef2ff;
  --cs-accent-100: #e0e7ff;
  --cs-accent-600: #4f46e5;
  --cs-accent-700: #4338ca;
  --cs-bg: #fbfaf7;            /* warm light */
  --cs-bg-2: #f4f1ec;
  --cs-surface: #ffffff;
  --cs-line: #e8e3da;
  --cs-line-2: #efeae2;
  --cs-text: #1c1917;
  --cs-text-2: #5a5347;
  --cs-text-3: #8c8472;
  --cs-sidebar-bg: #1c1c1c;
  --cs-sidebar-fg: #d6d3d1;
  --cs-sidebar-fg-dim: #8c8674;
  --cs-sidebar-hover: #2a2a2a;
  --cs-sidebar-active: #2a2a2a;
  --cs-green: #16a34a;
  --cs-green-bg: #dcfce7;
  --cs-red: #dc2626;
  --cs-red-bg: #fee2e2;
  --cs-amber: #d97706;
  --cs-amber-bg: #fef3c7;
  --cs-blue: #2563eb;
  --cs-blue-bg: #dbeafe;
  --cs-sky-bg: #e0f2fe;
  --cs-sky-fg: #0369a1;
  --cs-indigo-bg: #e0e7ff;
  --cs-indigo-fg: #4338ca;
  --cs-slate-bg: #f1f5f9;
  --cs-slate-fg: #475569;
  --cs-violet-bg: #ede9fe;
  --cs-violet-fg: #6d28d9;
  --cs-yellow-bg: #fef9c3;
  --cs-yellow-fg: #854d0e;
  --cs-radius: 14px;
  --cs-radius-sm: 10px;
  --cs-radius-lg: 20px;
  --cs-radius-btn: 10px;
  --cs-radius-input: 10px;
  --cs-radius-chip: 999px;
  --cs-shadow: 0 1px 2px rgba(15,15,15,.04), 0 1px 1px rgba(15,15,15,.03);
  --cs-shadow-md: 0 4px 12px rgba(15,15,15,.06), 0 1px 2px rgba(15,15,15,.04);
  --cs-shadow-lg: 0 12px 32px rgba(15,15,15,.10), 0 2px 6px rgba(15,15,15,.04);
  --cs-row-h: 36px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  color: var(--cs-text);
  background: var(--cs-bg);
  font-feature-settings: "ss01","cv11";
  -webkit-font-smoothing: antialiased;
}
.cs-root.cs-cool   { --cs-bg:#f8fafc; --cs-bg-2:#eef2f7; --cs-line:#e2e8f0; --cs-line-2:#eef2f7; }
.cs-root.cs-compact { --cs-row-h: 30px; }

.cs-root *, .cs-root *::before, .cs-root *::after { box-sizing: border-box; }
.cs-root button { font-family: inherit; }
.cs-root a { color: inherit; text-decoration: none; }
.cs-root [data-clickable] { cursor: pointer; }
.cs-root [data-clickable]:hover { background: var(--cs-bg-2); }

.cs-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: var(--cs-radius-btn); font-size: 13px; font-weight: 500;
  border: 1px solid var(--cs-line); background: var(--cs-surface);
  color: var(--cs-text); cursor: pointer; transition: background .12s, border-color .12s, box-shadow .12s;
  line-height: 1; white-space: nowrap;
}
.cs-btn:hover { background: var(--cs-bg-2); }
.cs-btn:focus-visible { outline: 2px solid var(--cs-accent); outline-offset: 2px; }
.cs-btn-primary { background: var(--cs-accent); color: #fff; border-color: var(--cs-accent); }
.cs-btn-primary:hover { background: var(--cs-accent-700); border-color: var(--cs-accent-700); }
.cs-btn-danger { background: var(--cs-red); color: #fff; border-color: var(--cs-red); }
.cs-btn-danger:hover { background: #b91c1c; }
.cs-btn-ghost { background: transparent; border-color: transparent; color: var(--cs-text-2); }
.cs-btn-ghost:hover { background: var(--cs-bg-2); color: var(--cs-text); }
.cs-btn-sm { padding: 4px 10px; font-size: 12px; }

.cs-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 12px; font-weight: 500; line-height: 18px;
  white-space: nowrap;
}
.cs-pill-md { padding: 3px 10px; font-size: 13px; line-height: 20px; }

@keyframes cs-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .55; } }
.cs-pulse { animation: cs-pulse 1.4s ease-in-out infinite; }
@keyframes cs-shimmer { 0% { background-position: -200px 0; } 100% { background-position: 200px 0; } }
.cs-skeleton {
  display: inline-block; border-radius: 4px;
  background: linear-gradient(90deg, var(--cs-line-2) 0%, #f8f6f1 50%, var(--cs-line-2) 100%);
  background-size: 200px 100%; animation: cs-shimmer 1.5s linear infinite;
}
.cs-tab { display:inline-flex; cursor:pointer; user-select:none; }

.cs-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
.cs-table thead th {
  text-align: left; font-weight: 500; color: var(--cs-text-3);
  padding: 8px 10px; border-bottom: 1px solid var(--cs-line);
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
  background: var(--cs-bg); position: sticky; top: 0;
}
.cs-table tbody td { padding: 10px; border-bottom: 1px solid var(--cs-line-2); vertical-align: middle; }
.cs-table tbody tr:hover { background: var(--cs-bg-2); }
.cs-num { font-variant-numeric: tabular-nums; }

.cs-card {
  background: var(--cs-surface);
  border: 1px solid var(--cs-line);
  border-radius: var(--cs-radius);
  box-shadow: var(--cs-shadow);
}

.cs-input {
  width: 100%; padding: 7px 10px; border-radius: var(--cs-radius-input);
  border: 1px solid var(--cs-line); background: var(--cs-surface);
  font-size: 13px; color: var(--cs-text); outline: none;
}
.cs-input:focus { border-color: var(--cs-accent); box-shadow: 0 0 0 3px var(--cs-accent-100); }

.cs-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: var(--cs-radius-chip); font-size: 13px;
  border: 1px solid var(--cs-line); background: var(--cs-surface);
  cursor: pointer; color: var(--cs-text-2);
}
.cs-chip:hover { background: var(--cs-bg-2); }
.cs-chip-active { border-color: var(--cs-accent); background: var(--cs-accent-50); color: var(--cs-accent-700); }

.cs-row-hover-actions { opacity: 0; transition: opacity .12s; }
.cs-table tbody tr:hover .cs-row-hover-actions { opacity: 1; }

.cs-link { color: var(--cs-accent); cursor: pointer; }
.cs-link:hover { text-decoration: underline; }
`;

if (typeof document !== 'undefined' && !document.getElementById('cs-styles')) {
  const s = document.createElement('style');
  s.id = 'cs-styles';
  s.textContent = css;
  document.head.appendChild(s);
}

// ── Lucide-ish inline icons ──────────────────────────────────────────────
// Single Icon component that renders by name; kept small. Stroke 1.75 for clean small sizes.
const Icon = ({ name, size = 16, color = 'currentColor', style }) => {
  const P = (children) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
         style={{ flexShrink: 0, ...style }} aria-hidden="true">
      {children}
    </svg>
  );
  switch (name) {
    case 'bar-chart-2':    return P(<><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></>);
    case 'file-text':      return P(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></>);
    case 'wallet':         return P(<><path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4"/><path d="M4 6v12c0 1.1.9 2 2 2h14v-4"/><path d="M18 12a2 2 0 0 0-2 2c0 1.1.9 2 2 2h4v-4z"/></>);
    case 'arrow-down-circle': return P(<><circle cx="12" cy="12" r="10"/><polyline points="8 12 12 16 16 12"/><line x1="12" y1="8" x2="12" y2="16"/></>);
    case 'arrow-up-circle':   return P(<><circle cx="12" cy="12" r="10"/><polyline points="16 12 12 8 8 12"/><line x1="12" y1="16" x2="12" y2="8"/></>);
    case 'trending-up':    return P(<><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></>);
    case 'trending-down':  return P(<><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></>);
    case 'chevron-down':   return P(<polyline points="6 9 12 15 18 9"/>);
    case 'chevron-up':     return P(<polyline points="18 15 12 9 6 15"/>);
    case 'chevron-right':  return P(<polyline points="9 18 15 12 9 6"/>);
    case 'chevron-left':   return P(<polyline points="15 18 9 12 15 6"/>);
    case 'arrow-left':     return P(<><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></>);
    case 'arrow-right':    return P(<><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>);
    case 'plus':           return P(<><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>);
    case 'search':         return P(<><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>);
    case 'check':          return P(<polyline points="20 6 9 17 4 12"/>);
    case 'check-circle':   return P(<><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>);
    case 'x':              return P(<><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>);
    case 'x-circle':       return P(<><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></>);
    case 'alert-circle':   return P(<><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>);
    case 'alert-triangle': return P(<><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></>);
    case 'info':           return P(<><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></>);
    case 'clock':          return P(<><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>);
    case 'loader':         return P(<><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></>);
    case 'more-vertical':  return P(<><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></>);
    case 'more-horizontal':return P(<><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>);
    case 'menu':           return P(<><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></>);
    case 'filter':         return P(<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>);
    case 'columns':        return P(<><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="3" x2="12" y2="21"/></>);
    case 'list':           return P(<><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></>);
    case 'upload-cloud':   return P(<><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/><polyline points="16 16 12 12 8 16"/></>);
    case 'file':           return P(<><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></>);
    case 'external-link':  return P(<><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></>);
    case 'refresh':        return P(<><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></>);
    case 'rotate-ccw':     return P(<><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></>);
    case 'download':       return P(<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></>);
    case 'trash':          return P(<><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></>);
    case 'edit-2':         return P(<><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></>);
    case 'play':           return P(<polygon points="5 3 19 12 5 21 5 3"/>);
    case 'pause':          return P(<><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></>);
    case 'square':         return P(<rect x="3" y="3" width="18" height="18" rx="2"/>);
    case 'check-square':   return P(<><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>);
    case 'calendar':       return P(<><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>);
    case 'dot':            return P(<circle cx="12" cy="12" r="3" fill="currentColor"/>);
    case 'settings':       return P(<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></>);
    case 'eye':            return P(<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>);
    case 'log-out':        return P(<><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></>);
    case 'help-circle':    return P(<><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></>);
    case 'inbox':          return P(<><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></>);
    case 'users':          return P(<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>);
    case 'corner-down-right': return P(<><polyline points="15 10 20 15 15 20"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/></>);
    case 'zap':            return P(<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>);
    case 'circle':         return P(<circle cx="12" cy="12" r="10"/>);
    case 'box':            return P(<><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></>);
    default: return P(<circle cx="12" cy="12" r="9"/>);
  }
};

// ── StatusPill ────────────────────────────────────────────────────────────
const STATUS_MAP = {
  'run-status': {
    'Draft':         { bg: '#e7e5e4', fg: '#44403c', icon: 'file' },
    'Parsed':        { bg: 'var(--cs-sky-bg)',    fg: 'var(--cs-sky-fg)',    icon: 'check' },
    'Validated':     { bg: 'var(--cs-blue-bg)',   fg: 'var(--cs-blue)',      icon: 'check-circle' },
    'Queued':        { bg: 'var(--cs-indigo-bg)', fg: 'var(--cs-indigo-fg)', icon: 'clock' },
    'Processing':    { bg: 'var(--cs-indigo-bg)', fg: 'var(--cs-indigo-fg)', icon: 'loader', pulse: true },
    'Completed':     { bg: 'var(--cs-green-bg)',  fg: '#15803d',             icon: 'check' },
    'Failed':        { bg: 'var(--cs-red-bg)',    fg: 'var(--cs-red)',       icon: 'x' },
    'Cancelled':     { bg: '#e7e5e4',             fg: '#44403c',             icon: 'x' },
    'Reverting':     { bg: 'var(--cs-amber-bg)',  fg: '#92400e',             icon: 'loader', pulse: true },
    'Reverted':      { bg: 'var(--cs-amber-bg)',  fg: '#92400e',             icon: 'rotate-ccw' },
    'Revert-Failed': { bg: 'var(--cs-red-bg)',    fg: '#991b1b',             icon: 'alert-circle' },
  },
  'row-validation': {
    'Valid':   { bg: 'var(--cs-green-bg)', fg: '#15803d', icon: 'check' },
    'Error':   { bg: 'var(--cs-red-bg)',   fg: 'var(--cs-red)', icon: 'x' },
    'Skipped': { bg: '#e7e5e4',            fg: '#44403c', icon: null },
  },
  'txn-type': {
    'Income':            { bg: '#f0fdf4',           fg: '#15803d' },
    'Expense':           { bg: '#fef2f2',           fg: '#b91c1c' },
    'Transfer':          { bg: 'var(--cs-slate-bg)', fg: 'var(--cs-slate-fg)' },
    'External Transfer': { bg: 'var(--cs-slate-bg)', fg: 'var(--cs-slate-fg)' },
    'Adjustment':        { bg: 'var(--cs-yellow-bg)', fg: 'var(--cs-yellow-fg)' },
    'Loan Receivable':   { bg: 'var(--cs-violet-bg)', fg: 'var(--cs-violet-fg)' },
    'Loan Payable':      { bg: 'var(--cs-violet-bg)', fg: 'var(--cs-violet-fg)' },
  },
};

const StatusPill = ({ kind, value, size = 'md' }) => {
  const m = STATUS_MAP[kind]?.[value];
  if (!m) return <span style={{ color: 'var(--cs-text-3)' }}>—</span>;
  const cls = `cs-pill ${size === 'md' ? 'cs-pill-md' : ''} ${m.pulse ? 'cs-pulse' : ''}`;
  return (
    <span className={cls} style={{ background: m.bg, color: m.fg }}>
      {m.icon && <Icon name={m.icon} size={size === 'md' ? 13 : 11} />}
      {value}
    </span>
  );
};

// ── AmountDisplay ─────────────────────────────────────────────────────────
const AmountDisplay = ({ amount, signed = false, signSource = null, compact = false, muted = false, big = false, style = {} }) => {
  if (amount == null) return <span style={{ color: 'var(--cs-text-3)' }}>—</span>;
  // Determine sign from source if given
  let display = amount;
  if (signed && signSource != null) {
    display = signSource > 0 ? Math.abs(amount) : -Math.abs(amount);
  }
  const text = window.fmtPKR(display, { signed, compact });
  const color = signed
    ? (display > 0 ? 'var(--cs-green)' : display < 0 ? 'var(--cs-red)' : 'var(--cs-text-2)')
    : (muted ? 'var(--cs-text-2)' : 'var(--cs-text)');
  const sz = big ? { fontSize: 28, fontWeight: 600, letterSpacing: '-0.01em' } : {};
  return <span className="cs-num" style={{ color, ...sz, ...style }}>{text}</span>;
};

// ── Tile ──────────────────────────────────────────────────────────────────
const Tile = ({ icon, label, amount, prior, accent, currency = 'PKR', big = true }) => {
  let deltaPct = null, deltaSign = 0;
  if (prior != null && prior !== 0) {
    deltaPct = ((amount - prior) / Math.abs(prior)) * 100;
    deltaSign = amount > prior ? 1 : (amount < prior ? -1 : 0);
  }
  const accentColor = accent || 'var(--cs-accent)';
  return (
    <div className="cs-card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 12,
          background: accentColor + '22',
          color: accentColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={icon} size={16} />
        </div>
        <span style={{ fontSize: 12, color: 'var(--cs-text-2)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1.1 }} className="cs-num">
        {window.fmtPKR(amount)}
      </div>
      {deltaPct != null ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 2,
            color: deltaSign > 0 ? 'var(--cs-green)' : deltaSign < 0 ? 'var(--cs-red)' : 'var(--cs-text-2)',
            fontWeight: 500,
          }}>
            <Icon name={deltaSign > 0 ? 'trending-up' : 'trending-down'} size={12} />
            {Math.abs(deltaPct).toFixed(1)}%
          </span>
          <span style={{ color: 'var(--cs-text-3)' }}>vs last period</span>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: 'var(--cs-text-3)' }}>Period net</div>
      )}
    </div>
  );
};

// ── Empty state ───────────────────────────────────────────────────────────
const EmptyState = ({ icon = 'inbox', title, body, primary, secondary }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 48, textAlign: 'center', gap: 12 }}>
    <div style={{ width: 72, height: 72, borderRadius: 24, background: 'var(--cs-bg-2)', color: 'var(--cs-text-3)', display:'flex', alignItems:'center', justifyContent:'center' }}>
      <Icon name={icon} size={32} />
    </div>
    <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--cs-text)' }}>{title}</div>
    {body && <div style={{ fontSize: 13, color: 'var(--cs-text-2)', maxWidth: 360, lineHeight: 1.5 }}>{body}</div>}
    {(primary || secondary) && (
      <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
        {primary && <button className="cs-btn cs-btn-primary"><Icon name="plus" size={14}/> {primary.label}</button>}
        {secondary && <button className="cs-btn cs-btn-ghost">{secondary.label}</button>}
      </div>
    )}
  </div>
);

// ── Skeleton ──────────────────────────────────────────────────────────────
const Skel = ({ w = '60%', h = 12, style = {} }) => (
  <span className="cs-skeleton" style={{ width: w, height: h, ...style }} />
);

// ── Bar (mini horizontal) ────────────────────────────────────────────────
const MiniBar = ({ value, max, color = 'var(--cs-accent)', height = 6 }) => (
  <div style={{ height, background: 'var(--cs-bg-2)', borderRadius: 999, overflow: 'hidden', width: '100%' }}>
    <div style={{ height: '100%', width: `${Math.max(2, (value/max)*100)}%`, background: color, borderRadius: 999 }} />
  </div>
);

Object.assign(window, { Icon, StatusPill, AmountDisplay, Tile, EmptyState, Skel, MiniBar, STATUS_MAP });
