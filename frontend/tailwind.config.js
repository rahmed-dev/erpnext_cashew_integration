import frappeUIPreset from 'frappe-ui/tailwind';

/** @type {import('tailwindcss').Config} */
export default {
  presets: [frappeUIPreset],
  content: [
    './src/**/*.{html,jsx,tsx,vue,js,ts}',
    './node_modules/frappe-ui/src/components/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        // f010 — c004 ThemeController sets these CSS vars on :root
        cs: {
          accent:        'var(--cs-accent)',
          'accent-700':  'var(--cs-accent-700)',
          'accent-100':  'var(--cs-accent-100)',
          'accent-50':   'var(--cs-accent-50)',
        },
      },
    },
  },
  plugins: [],
}
