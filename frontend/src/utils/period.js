// f010 — shared period→date-range resolution. Used by c005 + c007.

function pad(n) { return String(n).padStart(2, '0'); }
function iso(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }

function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function endOfMonth(d)   { return new Date(d.getFullYear(), d.getMonth() + 1, 0); }

export function resolvePeriodRange(period, customRange) {
  if (!period || period === 'any') return null;
  if (period === 'custom') {
    if (customRange?.start && customRange?.end) {
      return { start: customRange.start, end: customRange.end };
    }
    return null;
  }
  const today = new Date();
  if (period === 'this-month') {
    return { start: iso(startOfMonth(today)), end: iso(endOfMonth(today)) };
  }
  if (period === 'last-month') {
    const ref = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    return { start: iso(startOfMonth(ref)), end: iso(endOfMonth(ref)) };
  }
  if (period === 'last-3-months') {
    const startRef = new Date(today.getFullYear(), today.getMonth() - 2, 1);
    return { start: iso(startOfMonth(startRef)), end: iso(endOfMonth(today)) };
  }
  if (period === 'last-30-days') {
    const start = new Date(today); start.setDate(today.getDate() - 30);
    return { start: iso(start), end: iso(today) };
  }
  if (period === 'last-90-days') {
    const start = new Date(today); start.setDate(today.getDate() - 90);
    return { start: iso(start), end: iso(today) };
  }
  if (period === 'this-fiscal-year') {
    const fyStart = customRange?.fiscalYearStart;
    if (fyStart) return { start: fyStart, end: iso(today) };
    const ref = new Date(today.getFullYear(), 0, 1);
    return { start: iso(ref), end: iso(today) };
  }
  return null;
}

export const PERIOD_PRESET_LABELS = {
  'this-month': 'This Month',
  'last-month': 'Last Month',
  'last-30-days': 'Last 30 Days',
  'last-90-days': 'Last 90 Days',
  'this-fiscal-year': 'This Fiscal Year',
  'last-3-months': 'Last 3 Months',
  custom: 'Custom Range',
  any: 'Any time',
};

const SHORT_MONTH = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const LONG_MONTH = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function parseISO(s) {
  if (!s) return null;
  const [y, m, d] = s.split('-').map((p) => parseInt(p, 10));
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export function formatRange(start, end, format = 'short') {
  const s = parseISO(start);
  const e = parseISO(end);
  if (!s && !e) return null;
  const months = format === 'long' ? LONG_MONTH : SHORT_MONTH;
  const fmt = (d) => d ? `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}` : '—';
  if (s && e) {
    const sameYear = s.getFullYear() === e.getFullYear();
    if (sameYear && format === 'short') {
      return `${months[s.getMonth()]} ${s.getDate()} – ${months[e.getMonth()]} ${e.getDate()}, ${e.getFullYear()}`;
    }
    return `${fmt(s)} – ${fmt(e)}`;
  }
  return fmt(s || e);
}
