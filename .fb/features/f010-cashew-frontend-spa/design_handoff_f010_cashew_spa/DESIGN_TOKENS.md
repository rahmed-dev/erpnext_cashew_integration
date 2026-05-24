# Design Tokens — Cashew SPA

Every numeric / color value used in the prototype, in token form. Map these to Tailwind config (`tailwind.config.js` → `theme.extend.colors`, `borderRadius`, `boxShadow`) and use the resulting utility classes in the Vue SFCs.

The prototype expresses these as CSS custom properties on `.cs-root` in `design-reference/src/ui.jsx` — copy from there if you want the source of truth.

---

## Color

### Brand

| Token | Value | Use |
|---|---|---|
| `--cs-accent` | `#4f46e5` (indigo-600) | Primary CTAs, active nav, selected state, focus ring |
| `--cs-accent-700` | `#4338ca` | Hover state for primary CTA |
| `--cs-accent-100` | `#e0e7ff` | Focus ring background (`0 0 0 3px`) |
| `--cs-accent-50` | `#eef2ff` | Subtle accent fills (active chip, selected row, dropdown active item) |

The accent is tweakable in the prototype (5 presets: indigo, teal, burnt orange, monochrome, cyan). The build can expose this via a setting if desired; default is **indigo `#4f46e5`**.

### Surface & text (warm-white theme — default)

| Token | Value | Use |
|---|---|---|
| `--cs-bg` | `#fbfaf7` | App background (content area, inside cards) |
| `--cs-bg-2` | `#f4f1ec` | Subtle fills (hover row background, skeleton base, icon-tile backgrounds) |
| `--cs-surface` | `#ffffff` | Cards, modals, table backgrounds, inputs |
| `--cs-line` | `#e8e3da` | Primary border (cards, inputs, table heads) |
| `--cs-line-2` | `#efeae2` | Secondary border (row separators, dividers) |
| `--cs-text` | `#1c1917` | Primary text |
| `--cs-text-2` | `#5a5347` | Secondary text (subtitles, labels) |
| `--cs-text-3` | `#8c8472` | Tertiary text (captions, placeholders, em-dashes) |

### Cool-white theme (alternate)

| Token | Value |
|---|---|
| `--cs-bg` | `#f8fafc` |
| `--cs-bg-2` | `#eef2f7` |
| `--cs-line` | `#e2e8f0` |
| `--cs-line-2` | `#eef2f7` |

### Sidebar (always dark)

| Token | Value |
|---|---|
| `--cs-sidebar-bg` | `#1c1c1c` |
| `--cs-sidebar-fg` | `#d6d3d1` |
| `--cs-sidebar-fg-dim` | `#8c8674` |
| `--cs-sidebar-hover` | `#2a2a2a` |
| `--cs-sidebar-active` | `#2a2a2a` |

The active nav item has a 2px accent-colored stripe on the left edge.

### Functional / status

These drive status pills, banners, and amount sign. Don't repaint by page — they're system-wide signals.

| Family | bg | fg | use |
|---|---|---|---|
| **Green** | `#dcfce7` | `#15803d` | Valid, Completed, Income, positive deltas, "all valid" banner |
| **Red** | `#fee2e2` | `#dc2626` | Error, Failed, Expense, negative deltas, "rows have errors" banner |
| **Amber** | `#fef3c7` | `#92400e` | Reverted, Reverting, Cancelled |
| **Sky** | `#e0f2fe` | `#0369a1` | Parsed |
| **Blue** | `#dbeafe` | `#2563eb` | Validated |
| **Indigo** | `#e0e7ff` | `#4338ca` | Queued, Processing, "ready to queue" banner |
| **Slate** | `#f1f5f9` | `#475569` | Transfer, External Transfer |
| **Violet** | `#ede9fe` | `#6d28d9` | Loan Receivable, Loan Payable |
| **Yellow** | `#fef9c3` | `#854d0e` | Adjustment |
| **Stone** | `#e7e5e4` | `#44403c` | Draft, Cancelled, Skipped |

### Tile icon-tile accents (per balance tile)

The dashboard tiles use a colored icon chip on each:

| Tile | Color |
|---|---|
| Cash & Bank | `#0891b2` (cyan-600) |
| Receivable | `#16a34a` (green-600) |
| Payable | `#dc2626` (red-600) |
| Net This Period | `#4f46e5` (accent) |

Tile-icon container is `accent + "22"` (15% alpha overlay on the surface) with the icon at full accent.

---

## Typography

System UI stack — no webfonts.

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
             system-ui, sans-serif;
```

Mono (run IDs, posted doc names) — `ui-monospace, monospace`.

### Scale

| Use | Size | Weight | Letter-spacing | Notes |
|---|---|---|---|---|
| Page H1 | 24px / 1.2 | 600 | -0.01em | "Finance Dashboard", "Imports" |
| Run name (in workspace H1) | 20px | 600 | -0.01em | monospace family |
| Section H3 | 14px | 600 | normal | "Top Categories", "Income vs Expense" |
| Body | 13px / 1.5 | 400 | normal | Default text, table cells |
| Big number (tile) | 26px | 600 | -0.02em | tabular-nums |
| Big number (banner) | 18px | 600 | normal | tabular-nums |
| Donut center "Net" | 20px | 600 | normal | tabular-nums; up/down arrow inline |
| Caption (uppercase) | 11px | 600 | 0.06em | `text-transform: uppercase` — "CASH & BANK", "INCOME", "PERIOD" |
| Caption (sentence) | 12px | 500 | normal | "Updated 2h ago", subtitle text |
| Run ID | 12–13px | 400 | normal | ui-monospace |
| Pill text (md) | 13px | 500 | normal | StatusPill, line-height 20px |
| Pill text (sm) | 12px | 500 | normal | line-height 18px |

### Numeric rule

**Any column or label showing a money value or count uses `font-variant-numeric: tabular-nums`.** This is non-negotiable for finance UX — operators scan columns top-to-bottom.

### Currency formatting (PKR)

```js
new Intl.NumberFormat('en-PK', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(amount);
// → "1,524,500.00"
```

Prefixed with `Rs ` (no period). Sign character: `−` (U+2212), not `-`. Format:

- Default: `Rs 1,524,500.00`
- Signed positive: `+Rs 152,400.00` (green)
- Signed negative: `−Rs 88,350.00` (red)
- Compact (>1L): `Rs 1.5L` (lakh), `Rs 12.5Cr` (crore), `Rs 524K`
- Null / missing: `—` (em-dash) in `var(--cs-text-3)`

---

## Spacing

Lean on the Tailwind default scale (4px base). Don't invent new tokens.

| Use | Value |
|---|---|
| Tight (inline gaps, pill internal) | 4px (`gap-1`) |
| Compact (toolbar gap, inline icon gap) | 6px (`gap-1.5`) |
| Default (button gap, card internal gap) | 8px (`gap-2`) |
| Section internal | 12–16px (`gap-3` / `gap-4`) |
| Card padding | 18px (`p-[18px]`) for tiles · 14px for compact cards |
| Page padding | 20–28px (`p-5` / `p-7`) |
| Sidebar width | 224px expanded · 60px collapsed |

---

## Radius

The prototype exposes a `roundness` tweak. Default is `round`:

| Token | sharp | regular | **round (default)** | extra |
|---|---|---|---|---|
| `--cs-radius` (card) | 4px | 10px | **14px** | 24px |
| `--cs-radius-btn` | 4px | 8px | **10px** | 16px |
| `--cs-radius-input` | 4px | 8px | **10px** | 16px |
| `--cs-radius-chip` | 4px | 8px | **999px** | 999px |
| `--cs-radius-lg` (modal / dropzone) | 6px | 14px | **20px** | 32px |

Avatar / status dots: `999px` regardless. The active-nav stripe is 2px wide × variable height, `border-radius: 2px`.

---

## Shadow

| Token | Value | Use |
|---|---|---|
| `--cs-shadow` | `0 1px 2px rgba(15,15,15,.04), 0 1px 1px rgba(15,15,15,.03)` | Default card |
| `--cs-shadow-md` | `0 4px 12px rgba(15,15,15,.06), 0 1px 2px rgba(15,15,15,.04)` | Hover lift on import cards |
| `--cs-shadow-lg` | `0 12px 32px rgba(15,15,15,.10), 0 2px 6px rgba(15,15,15,.04)` | Dropdowns, modals, sticky bottom selection footer |

Shadows are functional, not decorative. Don't add a default shadow to inputs or chips.

---

## Density

Tweakable as `compact` / `comfortable` (default).

| Token | compact | comfortable |
|---|---|---|
| Table row height | 30px | 36–40px |
| Table cell padding (vertical) | 4px | 8px |
| Tile padding | unchanged | unchanged |

Density only affects the data grid — not chrome.

---

## Iconography

**Lucide** — `lucide-vue-next` (already pulled in via the vite plugin per arch D2).

Icon weights used:
- Default stroke 1.75
- Sizes: 11 (inside small pills), 13–14 (button), 16–18 (sidebar nav), 20 (active step), 26–32 (empty-state hero)
- Color: `currentColor` so it inherits from parent text color

Specific icons mapped to concepts (use consistently across pages):

| Concept | Icon |
|---|---|
| Dashboard nav | `bar-chart-2` |
| Imports nav | `file-text` |
| Cash & Bank tile | `wallet` |
| Receivable tile | `arrow-down-circle` |
| Payable tile | `arrow-up-circle` |
| Net tile | `trending-up` / `trending-down` |
| Refresh / re-validate | `refresh-cw` |
| Revert / undo | `rotate-ccw` |
| Inline edit | `edit-2` / `edit-3` |
| Open in Desk | `external-link` |
| Download | `download` |
| Confirm / valid | `check` / `check-circle` |
| Error / fail | `x` / `x-circle` / `alert-circle` |
| Warning (confirm dialog) | `alert-triangle` |
| Drag handle (drawer) | `grip-vertical` |
| Search | `search` |
| Filter | `filter` |
| Columns | `columns` |
| Live dot | `dot` (filled circle) |

---

## Motion

| Use | Duration | Easing |
|---|---|---|
| Hover (background, border, color) | 120ms | linear |
| Transform / shadow lift on hover | 150ms | `ease` |
| Status pill pulse (Processing / Reverting) | 1.4s | `ease-in-out`, infinite, opacity 1↔0.55 |
| Skeleton shimmer | 1.5s | linear, infinite, 200px gradient sweep |
| Sidebar collapse | 180ms | `ease` |
| Drawer collapse (split workbench alt) | 200ms | `ease` |
| Dropdown / popover appear | 120ms | `ease-out` |
| Realtime row pulse | 500ms | `ease-out`, border-highlight one-shot |

---

## Brand mark (Cashew icon)

Custom SVG (committed at `cashew_integration/public/images/cashew-app-icon.svg`).

The prototype uses an abstract "C-arc" placeholder — replace with the final asset. The icon container is 28×28 with 10–12px radius, accent background, white icon at ~18×18.

```svg
<svg viewBox="0 0 24 24" fill="none">
  <path d="M19 8.5c0-2-2-4-5-4-4.5 0-8 3.5-8 8 0 4 3 7.5 7 7.5 2.5 0 4.5-1.5 5-3.5"
        stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="17.5" cy="7" r="1.3" fill="currentColor"/>
</svg>
```

Use until the production icon is finalized. The app-icon route is also referenced by `hooks.py`:
```python
app_icon_url   = "/assets/cashew_integration/images/cashew-app-icon.svg"
app_icon_route = "/cashew"
app_icon_title = "Cashew"
```

---

## Responsive breakpoints

Tailwind defaults — no custom breakpoints needed:

| Breakpoint | Width | Behaviour summary |
|---|---|---|
| `<sm` (<640px) | mobile | sidebar collapsed to hamburger drawer; tables become card lists; filter bar collapses to bottom-sheet trigger |
| `sm` 640–767 | small tablet | tile grid 2-up; chart + categories stack |
| `md` 768–1023 | tablet | tile grid 4-up but smaller; chart + categories stack |
| `lg` 1024–1279 | small desktop | tile grid 4-up; chart 1/2 + categories 1/2 |
| `xl` ≥1280 | desktop | tile grid 4-up; chart 2/3 + categories 1/3; recent-imports strip shows 5 cards |

See each page spec under `spec/pages/*.md` for the per-component shift list.
