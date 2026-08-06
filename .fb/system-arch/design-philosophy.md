# Cashew SPA — Design Philosophy

Binding visual + interaction conventions for the `/cashew` Vue SPA (f010 and all
later frontend work). Codified 2026-06-02 after a run of UI bugs that all traced
back to the same few root causes. Read this before touching SPA styling.

## 1. Surfaces are opaque — never hand-force a background

frappe-ui components paint their surfaces through design tokens
(`bg-surface-modal`, `bg-surface-white`, dividers via `divide-outline-gray-*`,
text via `text-ink-gray-*`). These tokens **are** wired in this SPA — the
frappe-ui Tailwind preset is in `tailwind.config.js` and emits the `:root`
variables (`--surface-modal:#fff`, …) into the base layer. Verified in the built
`assets/index-*.css`.

- A menu/modal that looks "see-through" is **almost never** a missing background.
  Do not add `background-color:#fff` overrides to frappe-ui components — it masks
  the real cause and drifts from the theme.
- The real cause is nearly always **stacking** (§2).

## 2. Z-layer scale — the #1 recurring bug class

frappe-ui overlays render **inline** (Dialog) or **teleport to `body`**
(Dropdown) with **no z-index of their own**. App chrome that sets a z-index then
paints *over* the overlay, and the page appears to "bleed through" it.

Fixed, app-wide scale — **do not exceed these tiers**:

| Tier | z-index | Used by |
|------|---------|---------|
| Table sticky header | `z-10` | `RowsTable` `thead` |
| In-page chrome | `z-20` – `z-30` | sticky toolbars, filter panels |
| App nav | `z-40` | sidebar / mobile bottom nav |
| **Overlays** | **`z-50`** | dropdown menus, dialog overlays, drawers, toasts |

Enforced globally in `src/index.css`:
```css
.dropdown-content { z-index: 50; }  /* frappe-ui Dropdown (portaled to body)        */
.dialog-overlay   { z-index: 50; }  /* frappe-ui Dialog overlay + panel             */
.PopoverContent   { z-index: 50; }  /* frappe-ui Popover/Autocomplete (reka portal) */
```
**There are THREE overlay portal classes, not two** — every frappe-ui overlay
ships with **no z-index of its own** and must be pinned here. `.PopoverContent`
backs `<Popover>` AND `<Autocomplete>` (Autocomplete renders its list through
Popover). It was the class missed in the first pass: an Autocomplete opened
*inside* a Dialog rendered **behind** the modal, because `.dialog-overlay` had an
explicit `z-50` and the popover defaulted to `auto`. Equal `z-50` is deliberate —
the popover portal mounts after the dialog opens, so DOM order paints it on top.
When you add a new frappe-ui overlay, grep its source for the portal content
class and pin it to 50 here; do not assume the two original classes cover it.

Rules:
- Never give in-page chrome a z-index ≥ 50. If a toolbar needs to sit above the
  table, `z-20`/`z-30` is enough — going to `z-50` puts it over open modals.
- New overlay-type components get `z-50`, nothing higher.
- Don't add `relative z-*` to a container just to fix a child overlay — the
  overlay is teleported and won't inherit it; fix the overlay class instead.

## 3. Rounding scale (rounded design language)

| Element | Class |
|---------|-------|
| Cards, tables, modals, popovers, panels | `rounded-lg` |
| Inputs, selects, buttons, **checkboxes** | `rounded` |
| Pills, tags, filter chips, status badges | `rounded-full` |

Native checkboxes must carry `rounded border-gray-300 text-[var(--cs-accent)]
focus:ring-[var(--cs-accent)]` — square checkboxes break the language.

## 4. Icons — use the Button slots, never manual margins

frappe-ui `Button` aligns icons via the `iconLeft` / `iconRight` props (they fill
the `#prefix` / `#suffix` slots, vertically centered). Pass a lucide component:
```vue
<Button variant="outline" :icon-left="Columns" :icon-right="ChevronDown">View</Button>
```
Do **not** hand-place `<Icon :size="14" class="mr-1" />` inside the default slot —
it sits on the text baseline and looks misaligned. This was the toolbar bug.

## 5. Form controls — prefer frappe-ui over native

- Link/reference selectors → frappe-ui `<Autocomplete>` / `<Link>` with
  `reference_doctype` (routes through `search_link`, honors `get_query`). See
  CLAUDE.md "SPA API discipline".
- Buttons → frappe-ui `<Button>`. Inputs → frappe-ui `<Input>`.
- Native `<select>` / `<input>` are a last resort; if used, match the rounding +
  border + accent conventions above so they don't read as foreign.

## 6. Accent color

Single source: the `--cs-accent*` CSS variables on `:root` (set by the c004
ThemeController from `Cashew Settings.accent_color`). Reference them as
`var(--cs-accent)` or the `cs.accent` Tailwind color. Never hardcode the indigo
hex in a component.

**Charts are the one narrow exception (amended 2026-08-07, f012 Decision 4).**
Multi-series and categorical charts need 8–10 distinct hues, which cannot be
derived from a single accent without producing muddy or low-contrast adjacent
categories. Charts therefore draw from a **curated categorical ramp defined in
exactly one module**, consumed by the shared `<CsChart>` wrapper. That ramp is
the only sanctioned non-accent colour source in the SPA; no chart, no component,
and no page may hardcode a hex outside it. The accent remains the primary and
emphasis colour — single-series charts, highlights, selection, hover. Income,
expense, and transfer carry fixed semantic colours that must not change hue
between charts.

## 7. Density & spacing

- Section gaps: `space-y-3` / `space-y-4`. Card padding: `p-3` (compact rows) to
  `p-5` (modals).
- Tables are compact: `px-2 py-1.5` cells, `text-sm`, `text-xs` for secondary
  lines. Keep it scannable; don't inflate row height.

## 8. Affordance placement

Primary row actions are **visible at the row**, not hidden in a kebab. The kebab
holds only secondary/rare actions. (The "Fix" action on error rows is a
first-class red button on the row; the kebab keeps Re-validate / View JSON /
Open posted.)

---
*When a styling fix feels like it needs `!important`, a forced background, or a
z-index above 50 — stop. It's almost certainly §2 (stacking) or §1 (mis-blamed
transparency). Re-diagnose against this doc first.*
