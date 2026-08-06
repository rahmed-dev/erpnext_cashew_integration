// f012 c001 — the chart theme owned by <CsChart>.
//
// Every chart in the SPA is drawn through <CsChart>, which merges the base
// option below under whatever the calling component supplies. Callers provide
// series, axes data and their own tooltip formatter; they never restate fonts,
// palette, grid colours or tooltip chrome, and they never build an ECharts
// option object outside a chart component (Decision 1).
import { RAMP, SEMANTIC, CHROME, alpha, alphaToken, accent } from '@/charts/palette';
import { formatAmount, formatCompactNumber, formatNumber } from '@/utils/money';

export { RAMP, SEMANTIC, CHROME, alpha, alphaToken, accent };

const FONT_STACK =
  'InterVar, Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * The base option every chart inherits.
 *
 * The tooltip sits in the z-50 overlay band on purpose: design-philosophy.md
 * point 2 fixes the scale (app nav 40, overlays 50) and ECharts renders its
 * tooltip into its own DOM layer, which would otherwise float above every
 * dialog in the app.
 */
export function baseOption() {
  return {
    color: RAMP,
    animationDuration: prefersReducedMotion() ? 0 : 500,
    textStyle: { fontFamily: FONT_STACK, color: CHROME.textMuted, fontSize: 11 },
    tooltip: {
      backgroundColor: CHROME.surface,
      borderColor: CHROME.border,
      borderWidth: 1,
      padding: [7, 10],
      textStyle: { color: CHROME.text, fontSize: 12 },
      extraCssText: 'z-index:50;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.12);',
    },
  };
}

/** Value axis formatted as short-form money — `Rs`-less, axes are unlabelled by convention. */
export function moneyAxis(currency = 'PKR', overrides = {}) {
  return {
    type: 'value',
    axisLine: { lineStyle: { color: CHROME.border } },
    axisTick: { show: false },
    axisLabel: {
      color: CHROME.axis,
      fontSize: 10,
      formatter: (v) => formatCompactNumber(v, currency),
    },
    splitLine: { lineStyle: { color: CHROME.grid } },
    ...overrides,
  };
}

/** Category axis with the shared axis chrome. `data` is already-formatted labels. */
export function categoryAxis(data, overrides = {}) {
  return {
    type: 'category',
    data,
    axisLine: { lineStyle: { color: CHROME.border } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { color: CHROME.axis, fontSize: 10 },
    ...overrides,
  };
}

/** Currency formatters bound to one currency, for use inside chart formatters. */
export function moneyFormatters(currency = 'PKR') {
  return {
    money: (v) => formatAmount(v, currency, { decimals: 0 }),
    moneyExact: (v) => formatAmount(v, currency),
    compact: (v) => formatCompactNumber(v, currency),
    plain: (v, decimals = 0) => formatNumber(v, currency, decimals),
  };
}

/** A tooltip row: `<marker> label ......... value`. */
export function tooltipRow(marker, label, value) {
  return (
    `<div style="display:flex;gap:12px;justify-content:space-between">` +
    `<span>${marker}${label}</span>` +
    `<b style="font-variant-numeric:tabular-nums">${value}</b>` +
    `</div>`
  );
}

/** Bold heading line inside a tooltip. */
export function tooltipTitle(text) {
  return `<div style="font-weight:600;margin-bottom:4px">${text}</div>`;
}

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/**
 * Deep-merge the caller's option over the base theme. Arrays are REPLACED, not
 * merged — a caller's `series` or `color` array is always authoritative.
 */
export function mergeOption(base, override) {
  if (!isPlainObject(override)) return override === undefined ? base : override;
  const out = { ...base };
  for (const [key, value] of Object.entries(override)) {
    out[key] = isPlainObject(value) && isPlainObject(base[key]) ? mergeOption(base[key], value) : value;
  }
  return out;
}
