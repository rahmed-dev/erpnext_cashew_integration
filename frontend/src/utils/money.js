// Currency formatting shared by <AmountDisplay> and the chart theme (f012 c001).
//
// Extracted so a chart tooltip and a balance tile can never disagree on how the
// same figure reads. PKR/INR use lakh/crore short forms because that is what the
// site's users read; everything else falls back to Intl compact notation.

export const LOCALES = { PKR: 'en-PK', INR: 'en-IN', USD: 'en-US', EUR: 'en-DE', GBP: 'en-GB' };
export const PREFIX = { PKR: 'Rs ', INR: '₹ ', USD: '$', EUR: '€', GBP: '£' };

export function localeFor(currency) {
  return LOCALES[currency] || 'en-US';
}

export function prefixFor(currency) {
  return PREFIX[currency] || '';
}

/** Plain grouped number, no currency prefix. */
export function formatNumber(value, currency = 'PKR', decimals = 2) {
  return new Intl.NumberFormat(localeFor(currency), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Short form for axis labels and dense tiles: 12.3L, 1.2Cr, 45K, 1.2M. */
export function formatCompactNumber(value, currency = 'PKR') {
  const locale = localeFor(currency);
  const abs = Math.abs(value);
  if (currency === 'PKR' || currency === 'INR') {
    if (abs >= 1e7) return `${(value / 1e7).toFixed(1)}Cr`;
    if (abs >= 1e5) return `${(value / 1e5).toFixed(1)}L`;
    if (abs >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
    return new Intl.NumberFormat(locale).format(value);
  }
  return new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

/**
 * Currency-prefixed amount.
 * `compact` swaps to the short form; `decimals` only applies to the long form.
 */
export function formatAmount(value, currency = 'PKR', { compact = false, decimals = 2 } = {}) {
  const body = compact
    ? formatCompactNumber(value, currency)
    : formatNumber(value, currency, decimals);
  return `${prefixFor(currency)}${body}`;
}
