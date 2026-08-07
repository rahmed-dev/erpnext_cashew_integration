// The dashboard's bucket-width vocabulary, in one place.
//
// Before this existed, every time-series chart carried its own
// `const isDaily = series.granularity === 'daily'` and its own ternary for the
// subtitle and the x-axis label. That was two-valued by accident rather than by
// design: adding weekly or yearly meant every chart quietly rendering a week as
// if it were a month, with nothing to catch it. The server now settles ONE width
// for the whole period (see `dashboard_series.resolve_granularity`) and every
// chart reads it through the helpers here, so a new width is added once.
//
// Nothing in this file decides anything. The choice is the server's — these are
// only the names and formats the client puts on it.

export const GRANULARITY_AUTO = 'auto';

/** The widths a surface may ask for, narrowest first, plus `auto`. */
export const GRANULARITY_OPTIONS = [
  { value: GRANULARITY_AUTO, label: 'Automatic', hint: 'Chosen from the period length' },
  { value: 'daily', label: 'Daily', hint: 'One point per day' },
  { value: 'weekly', label: 'Weekly', hint: 'One point per week, Monday to Sunday' },
  { value: 'monthly', label: 'Monthly', hint: 'One point per calendar month' },
  { value: 'yearly', label: 'Yearly', hint: 'One point per calendar year' },
];

const ADJECTIVE = {
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
  yearly: 'Yearly',
};

const NOUN = {
  daily: 'day',
  weekly: 'week',
  monthly: 'month',
  yearly: 'year',
};

/** "Daily" / "Weekly" / … — the word a chart subtitle opens with. */
export function granularityAdjective(series) {
  return ADJECTIVE[series?.granularity] || 'Daily';
}

/** "day" / "week" / … — for "one bar per {noun}" phrasing. */
export function granularityNoun(series) {
  return NOUN[series?.granularity] || 'day';
}

/** The picker's own label, which must reflect what was DRAWN, not what was asked. */
export function granularityLabel(series) {
  if (!series) return 'Automatic';
  if (series.granularity_auto) return `Auto · ${ADJECTIVE[series.granularity] || ''}`.trim();
  return ADJECTIVE[series.granularity] || 'Automatic';
}

/**
 * Set when the server refused the requested width because it would have made
 * too many buckets, and widened it instead. Surfaces say so rather than letting
 * the control disagree with the chart under it.
 */
export function granularityWasWidened(series) {
  return Boolean(series?.granularity_capped);
}

const SHORT_MONTH = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function parseKey(key) {
  if (!key) return null;
  const [y, m, d] = String(key).split('-').map((p) => parseInt(p, 10));
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

/**
 * The x-axis tick for one bucket at the current width.
 *
 * The server already ships a `label` per bucket and it is the fallback here, but
 * the daily label is an ISO date — correct in a tooltip, far too wide as an axis
 * tick — so the axis reformats rather than the server shipping two labels.
 */
export function bucketAxisLabel(bucket, series) {
  if (!bucket) return '';
  const g = series?.granularity;
  const d = parseKey(bucket.key);
  if (!d) return bucket.label || '';
  if (g === 'daily') return `${d.getDate()} ${SHORT_MONTH[d.getMonth()]}`;
  if (g === 'weekly') return `${d.getDate()} ${SHORT_MONTH[d.getMonth()]}`;
  if (g === 'yearly') return String(d.getFullYear());
  return bucket.label || `${SHORT_MONTH[d.getMonth()]} ${d.getFullYear()}`;
}

/**
 * The bucket's name in a tooltip — wider than the axis tick, because there is
 * room and because a week needs its span stated to mean anything.
 */
export function bucketTooltipLabel(bucket, series) {
  if (!bucket) return '';
  const g = series?.granularity;
  const start = parseKey(bucket.start || bucket.key);
  const end = parseKey(bucket.end);
  if (g === 'weekly' && start && end) {
    const sameMonth = start.getMonth() === end.getMonth();
    const left = `${start.getDate()} ${SHORT_MONTH[start.getMonth()]}`;
    const right = sameMonth
      ? `${end.getDate()}`
      : `${end.getDate()} ${SHORT_MONTH[end.getMonth()]}`;
    return `${left} – ${right} ${end.getFullYear()}`;
  }
  if (g === 'daily' && start) {
    return start.toLocaleDateString(undefined, {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
    });
  }
  return bucket.label || bucket.key || '';
}
