// f012 c001 — the single sanctioned non-accent colour source for the SPA.
//
// Decision 4 (locked 2026-08-07): multi-series and categorical charts draw from
// this curated 10-hue ramp; the Cashew accent (`--cs-accent*`) stays the primary
// and emphasis colour for single-series charts, highlights and selection. This
// narrowly amends design-philosophy.md point 6 — charts may use the named ramp
// defined here, it lives in exactly one file, and no chart may hardcode a hex
// outside it.
//
// Slot 1 is indigo so a single-series chart and the ramp's first category agree
// on the default Indigo accent. If the user picks a different accent the ramp
// does NOT retint — the accent still governs emphasis.
//
// NO DARK MODE (C5.6). The ramp's dark column recorded in decisions.md is a
// forward asset, not a deliverable; the SPA has zero `dark:` utilities.

export const RAMP = [
  '#4f46e5', // 1 indigo
  '#0d9488', // 2 teal
  '#d97706', // 3 amber
  '#e11d48', // 4 rose
  '#7c3aed', // 5 violet
  '#0891b2', // 6 cyan
  '#65a30d', // 7 lime
  '#ea580c', // 8 orange
  '#be185d', // 9 pink
  '#475569', // 10 slate
];

// Fixed meanings across EVERY chart — income/expense/transfer must not swap hue
// between the trend chart and the sankey.
export const SEMANTIC = {
  income: '#0f9d76',
  expense: '#e11d48',
  transfer: '#8b8d98',
};

// Neutral chrome used by the chart theme. Kept here so the theme module holds no
// hexes of its own.
export const CHROME = {
  text: '#1f2937',
  textMuted: '#4b5563',
  textFaint: '#9ca3af',
  axis: '#9ca3af',
  grid: '#f1f2f4',
  border: '#e5e7eb',
  surface: '#ffffff',
  surfaceAlt: '#f4f5f7',
};

const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** Ramp colour for an index, wrapping at 10. */
export function rampColor(i) {
  return RAMP[((i % RAMP.length) + RAMP.length) % RAMP.length];
}

/**
 * Read a CSS custom property off `:root`.
 * Falls back to `fallback` during SSR or before the theme controller has run.
 */
export function readToken(name, fallback = '') {
  if (typeof window === 'undefined' || typeof document === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** The live accent shades, as set by ThemeController (`src/theme.js`). */
export function accent() {
  return {
    base: readToken('--cs-accent', '#4f46e5'),
    dark: readToken('--cs-accent-700', '#4338ca'),
    light: readToken('--cs-accent-100', '#e0e7ff'),
    lightest: readToken('--cs-accent-50', '#eef2ff'),
  };
}

/**
 * Build an `rgba()` string from a hex colour.
 *
 * TRAP (Decision 4, proven while building the demo): zrender parses colours
 * itself and does NOT understand CSS `color-mix()`. Every translucent fill —
 * area gradients, axis-pointer shadows — must be built as rgba() from the token
 * hex, or it renders BLACK, silently. Always go through this helper.
 */
export function alpha(hex, a) {
  let h = String(hex || '').trim().replace('#', '');
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  const n = Number.parseInt(h, 16);
  if (h.length !== 6 || Number.isNaN(n)) return `rgba(120, 120, 140, ${a})`;
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

/** rgba() built from a CSS custom property — `alphaToken('--cs-accent', 0.3)`. */
export function alphaToken(name, a, fallback = '#4f46e5') {
  const value = readToken(name, fallback);
  return HEX_RE.test(value) ? alpha(value, a) : alpha(fallback, a);
}
