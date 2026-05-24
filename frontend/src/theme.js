import { hex2hsl, hsl2hex } from './colorUtils';

// Tailwind 3.x palette values — D14.b lock.
export const PRESET_TABLE = {
  Indigo:         ['#4f46e5', '#4338ca', '#e0e7ff', '#eef2ff'],
  Teal:           ['#0d9488', '#0f766e', '#ccfbf1', '#f0fdfa'],
  'Burnt Orange': ['#ea580c', '#c2410c', '#ffedd5', '#fff7ed'],
  Monochrome:     ['#1f2937', '#111827', '#e5e7eb', '#f3f4f6'],
  Cyan:           ['#0891b2', '#0e7490', '#cffafe', '#ecfeff'],
};

const VAR_NAMES = ['--cs-accent', '--cs-accent-700', '--cs-accent-100', '--cs-accent-50'];
const HEX_RE = /^#[0-9a-fA-F]{6}$/;

// Amendment 1 §4 — HSL math for Custom hex.
export function deriveShades(hex) {
  const [h, s, l] = hex2hsl(hex);
  return [
    hex,
    hsl2hex(h, s, Math.max(0, l - 10)),
    hsl2hex(h, Math.min(s, 30), 92),
    hsl2hex(h, Math.min(s, 20), 96),
  ];
}

function applyToRoot(shades) {
  const root = document.documentElement;
  VAR_NAMES.forEach((name, i) => root.style.setProperty(name, shades[i]));
}

export const ThemeController = {
  apply(accentColor, accentColorCustom) {
    let shades;
    if (accentColor === 'Custom' && HEX_RE.test(accentColorCustom || '')) {
      shades = deriveShades(accentColorCustom);
    } else if (PRESET_TABLE[accentColor]) {
      shades = PRESET_TABLE[accentColor];
    } else {
      shades = PRESET_TABLE.Indigo;
    }
    applyToRoot(shades);
  },
  init() {
    const settings = (typeof window !== 'undefined' && window.boot && window.boot.cashew_settings) || {};
    this.apply(settings.accent_color, settings.accent_color_custom);
  },
};

// c008 hook — called from Cashew Settings doc_update.
export function applyThemeFromDoc(settingsDoc) {
  ThemeController.apply(settingsDoc.accent_color, settingsDoc.accent_color_custom);
}
