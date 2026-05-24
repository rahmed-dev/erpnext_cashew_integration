# Page: Settings

> **Stack:** Vue 3 SPA (frappe-ui)
> **Component ID:** `c012` (`settings-page`)
> **Route:** `/settings`
> **Shell:** see [`../shell.md`](../shell.md) — sidebar + app switcher always present around this page
> **Arch refs:** D5 (API discipline), D6 (session-only view state), D12 (Settings page), D13 (schema additions), D14 (accent color storage)

---

## 1. Page brief (for Claude Design)

A **light-weight Settings page** that lives at `/settings` in the SPA. Operators and managers reach it from the third sidebar nav item below "Imports". The page solves two needs:

1. **Pick the app's accent color** (theme picker, 5 presets). Whatever the user picks immediately re-themes the SPA and persists on save. The choice is app-wide — every user sees the same accent next time they load the SPA.
2. **Set the default Company** that new imports inherit. This is the existing `Cashew Settings.company` field, surfaced inline instead of forcing the operator to open the Desk form.

For everything else that lives on Cashew Settings (mapping tables, future global settings), the page exposes a clearly-labeled "Manage on Desk →" deep-link. Mapping CRUD intentionally stays on Desk in f010 v1.

**Tone:** quiet, utilitarian, minimal chrome. This is a configuration page, not a primary working surface. Operators visit rarely. Visual restraint is a feature.

**Inspirations** (designer reference): Linear Settings pane (section bands + sentence-style helper copy); Notion's Appearance settings (preset chips with live preview); GitHub Settings forms (dirty-state save bar at the bottom).

---

## 2. Permission model

Cashew Settings has these permission roles (per doctype JSON):

| Role | Read | Write |
|---|---|---|
| System Manager | ✓ | ✓ |
| Accountant | ✓ | ✗ |

**Behavior:**
- The page renders for both roles (no route gating; D5.c shell-level only).
- **Write permission detected at load time** via `frappe.client.has_permission('Cashew Settings', 'Cashew Settings', 'write')` OR a `can_write_settings` flag baked into the boot dict (TD picks the cheaper path).
- If `can_write_settings === false`:
  - All inputs render disabled (`<Input disabled>`, `<Autocomplete disabled>`, preset chips greyed).
  - Save bar is not rendered.
  - A subtle banner above the Appearance section reads `Read-only: ask a System Manager to change these settings.`
- If `can_write_settings === true`: full edit + save flow.

---

## 3. Layout

Vertical single-column page. Max content width 720px (centered) — narrower than other pages because the inputs are small.

```
┌────────────────────────────────────────────────────────────┐
│ A. Page Header                                             │
│   Title: "Settings"                                        │
│   Subtitle: "App-wide configuration for Cashew."           │
├────────────────────────────────────────────────────────────┤
│ B. (banner — only when read-only)                          │
│   "Read-only — ask a System Manager to change settings."   │
├────────────────────────────────────────────────────────────┤
│ C. Section: Appearance                                     │
│   ┌─ Section heading + helper text ─┐                      │
│   │ Accent color                    │                      │
│   │ [chip] [chip] [chip] [chip] [chip]   (5 presets)       │
│   │ Helper: "Used across buttons, links, charts & focus."  │
│   └──────────────────────────────────┘                     │
├────────────────────────────────────────────────────────────┤
│ D. Section: Defaults                                       │
│   ┌─ Section heading + helper text ─┐                      │
│   │ Default Company                 │                      │
│   │ [Autocomplete: Company]         │                      │
│   │ Helper: "Pre-selected when creating a new import."     │
│   └──────────────────────────────────┘                     │
├────────────────────────────────────────────────────────────┤
│ E. Section: Mappings (Desk-managed)                        │
│   ┌─ Section heading + helper text ─┐                      │
│   │ Cashew Category Mapping  [Manage on Desk →]            │
│   │ Cashew Account Mapping   [Manage on Desk →]            │
│   │ Helper: "Mapping tables are managed in the Desk form." │
│   └──────────────────────────────────┘                     │
├────────────────────────────────────────────────────────────┤
│ F. Save Bar (sticky-bottom, visible only when dirty)       │
│   "Unsaved changes."  [Discard]  [Save Changes]            │
└────────────────────────────────────────────────────────────┘
```

**Responsive collapse:**
- ≥640px: as drawn, content width 720px max, page padding `p-7`.
- <640px: full-width content, page padding `p-5`. Preset chip row wraps to 2 lines (3 + 2). Save bar grows to full width.

---

## 4. Components

### A. PageHeader

Reuses `shared/PageHeader` per `../shared-components.md`.

| Element | Value |
|---|---|
| Title | `Settings` |
| Subtitle | `App-wide configuration for Cashew.` |
| Right slot | empty (no action button) |

### B. ReadOnlyBanner *(conditional)*

Renders **only** when `can_write_settings === false`.

| Element | Value |
|---|---|
| Container | Soft amber background card, full-width above section C |
| Icon | lucide `lock` (16px, currentColor) |
| Text | `Read-only — ask a System Manager to change settings.` |
| Size | small; minimal vertical padding |

### C. Appearance section

**Section heading:**
- Heading text: `Appearance`
- Helper text (below heading): `Choose the accent color used for buttons, links, charts and focus rings.`

**Body — AccentColorPicker (new shared component `AccentColorPicker.vue`):**

Horizontally-laid-out group of 5 preset chips. Each chip:

| Element | Description |
|---|---|
| Color swatch | 36×36px rounded rect filled with the preset's `--cs-accent` |
| Label | preset name below the swatch, 12px caption |
| Selected state | thicker border (2px solid `--cs-accent`) + small check icon top-right of swatch |
| Hover state | subtle ring around the swatch (`ring-2 ring-offset-1`) |
| Disabled state | 50% opacity + `cursor: not-allowed` |
| Click | sets local component value AND immediately writes the 4 CSS custom properties on `<html>` (live preview). Marks form dirty. |

**Preset list (matches D14 token table):**

| Preset | Swatch | Label |
|---|---|---|
| Indigo (default) | `#4f46e5` | `Indigo` |
| Teal | TD-picks teal-600 | `Teal` |
| Burnt Orange | TD-picks orange-600 | `Burnt Orange` |
| Monochrome | `#1f2937` | `Monochrome` |
| Cyan | TD-picks cyan-600 | `Cyan` |

**Props:**

| Prop | Type | Required | Notes |
|---|---|---|---|
| `modelValue` | `"Indigo" \| "Teal" \| "Burnt Orange" \| "Monochrome" \| "Cyan"` | yes | Current preset name from `Cashew Settings.accent_color` |
| `disabled` | boolean | no — default `false` | Read-only mode |

**Emits:**
- `update:modelValue` — on chip click, emits new preset name. Page handler: (1) updates local form state, (2) calls a shell-exposed `applyAccentTheme(presetName)` composable to live-paint the CSS variables, (3) sets form dirty.

**A11y:** Group rendered as `<div role="radiogroup" aria-label="Accent color">`; each chip is `<button role="radio" aria-checked={selected}>`.

**Behavior on form discard (see F):** Page calls `applyAccentTheme(originalAccent)` to revert the live preview before resetting form state.

### D. Defaults section

**Section heading:**
- Heading text: `Defaults`
- Helper text: `Default values that pre-fill when starting a new import.`

**Body — CompanyDefault row:**

| Element | Value |
|---|---|
| Label | `Default Company` |
| Input | frappe-ui `<Autocomplete reference_doctype="Company">` |
| Bound to | `Cashew Settings.company` |
| Helper text (below input) | `Pre-selected when creating a new import from /runs/new.` |
| State (read-only) | disabled, helper text reads value or `Not set` |
| Width | input takes 50% of section width on desktop, full on mobile |

**A11y:** `<label for>` pairs the visible label to the Autocomplete input id.

### E. Mappings section (Desk-managed)

**Section heading:**
- Heading text: `Mappings`
- Helper text: `Mapping tables are managed in the Desk form for now.`

**Body — two DeskLinkRow items:**

Each row renders as a list-item-style div with the doctype label on the left and a link button on the right.

| Row | Label | Sub-label | Action |
|---|---|---|---|
| 1 | `Cashew Category Mapping` | `Map Cashew categories to Frappe Accounts.` | `Manage on Desk →` button → `/app/cashew-category-mapping` (same tab) |
| 2 | `Cashew Account Mapping` | `Map Cashew accounts to Frappe Accounts.` | `Manage on Desk →` button → `/app/cashew-account-mapping` (same tab) |

**Visual:** Light subdued background card per row. lucide `external-link` icon (12px) inside the link button.

**Behavior:** Same-tab navigation. User returns via Back-to-Desk app-switcher item once finished.

### F. Save Bar

Sticky to the bottom of the viewport when the form is dirty AND the user is on this route. Renders only when:
- `can_write_settings === true`
- form `isDirty === true`

| Element | Value |
|---|---|
| Container | Full-width strip, white bg, `border-t`, `shadow-up-sm` |
| Left text | `Unsaved changes.` (small, sentence-case, `text-gray-700`) |
| Right buttons | `[Discard]` (variant=ghost) + `[Save Changes]` (variant=primary) |
| Save button busy state | label flips to `Saving…`, `aria-busy=true`, disabled |
| Save button success | toast `Settings saved.` (auto-dismiss 3s) |
| Save button error | toast with error message; button re-enables |

**Discard behavior:**
- Confirmation dialog (`shared/ConfirmDialog` info variant) — message: `Discard unsaved settings changes?`
- On confirm: revert all form fields to original values AND call `applyAccentTheme(originalAccent)` to roll back live preview.

**Navigate-away protection:**
- When dirty and user clicks another sidebar route or browser back: open the same Discard confirmation. Wire via `beforeRouteLeave` hook.

---

## 5. Data sources

### Read (on mount)

Single call:
```js
frappe.client.get_doc('Cashew Settings', 'Cashew Settings')
  // returns { name, company, accent_color, cashew_category_mapping, cashew_account_mapping, ... }
```

The mapping child tables are returned but not used by the SPA — they're managed on Desk.

Permission flag — TD picks one of:
- **Option A (cheaper):** boot dict injection in `cashew_integration/www/cashew.py` adds `can_write_settings = frappe.has_permission('Cashew Settings', 'write')`. Read once at SPA boot, cached in shell store.
- **Option B:** `frappe.client.has_permission` round-trip on Settings page mount. Trades a request for not bloating boot.

### Write (on Save)

`frappe.client.set_value('Cashew Settings', 'Cashew Settings', {company, accent_color})` — single call, both fields together. Per D5.1 (read/set value path; binds to existing Frappe perm system, no new endpoint).

On 403 (permission lost between load and save): error toast `Permission denied. Settings were not changed.` Form stays dirty so user can retry or discard.

### Boot dict additions

`cashew_integration/www/cashew.py` — add:
```python
"accent_color": frappe.db.get_single_value("Cashew Settings", "accent_color") or "Indigo",
"can_write_settings": frappe.has_permission("Cashew Settings", "write"),
```

### Realtime

Per D14:
- Shell subscribes to `Cashew Settings` `doc_update`.
- On event: shell reads new `accent_color` and calls `applyAccentTheme(newValue)`.
- Other open SPA tabs re-theme without reload.

---

## 6. States

| State | Trigger | UI |
|---|---|---|
| Loading | initial mount, awaiting `get_doc` | All sections render skeletons (heading + 1 row of skeleton blocks each) |
| Loaded — clean | `get_doc` resolved, form not yet touched | Sections populated; Save Bar hidden |
| Loaded — dirty | user changed any field | Save Bar appears (sticky bottom). Form fields show current local value. Accent preview already applied live. |
| Saving | user clicked Save | Save button busy state; other inputs disabled while in flight |
| Saved | server responded ok | Toast `Settings saved.`; Save Bar slides away; form returns to clean |
| Error | server 4xx/5xx | Toast with error message; Save Bar stays; button re-enabled |
| Read-only | `can_write_settings === false` | All inputs disabled; ReadOnlyBanner visible; Save Bar never appears |

---

## 7. Interactions

| Trigger | Effect |
|---|---|
| Click accent preset chip | Updates form value; live-applies CSS vars to `<html>`; marks dirty |
| Type into / pick from Company Autocomplete | Updates form value; marks dirty |
| Click `Manage on Desk →` (mappings) | Same-tab navigate to Desk route; SPA discards dirty state IF form clean. If dirty → first prompts the Discard dialog. |
| Click Save (dirty) | Calls `set_value`; on success closes Save Bar + toast; on error keeps bar open |
| Click Discard (dirty) | Opens ConfirmDialog; on confirm reverts form + reverts theme preview |
| `Esc` in Save Bar | Equivalent to Discard click |
| Navigate to a different SPA route while dirty | beforeRouteLeave → Discard confirmation |
| Receive realtime `Cashew Settings` doc_update | Shell re-themes globally; if Settings page is currently mounted AND not dirty, refetch and re-render form. If dirty: show a small inline notice `Settings changed in another tab. Discard to refresh.` |

---

## 8. Accessibility

| Concern | Pattern |
|---|---|
| Page landmark | `<main aria-labelledby="settings-h1">` |
| Section structure | each section uses `<section aria-labelledby="...-h2">` |
| Heading order | `<h1>Settings</h1>` (page) → `<h2>` per section |
| AccentColorPicker | `<div role="radiogroup" aria-label="Accent color">`; chips `<button role="radio" aria-checked>` |
| Read-only state | aria-disabled on container; ReadOnlyBanner is `role="status"` |
| Save Bar | `role="region" aria-label="Unsaved changes"`. Save button busy → `aria-busy=true`, label change to `Saving…` |
| Discard confirm | inherits ConfirmDialog `role="dialog" aria-modal="true"` |
| Live preview | When theme changes, fire a screen-reader announcement (`aria-live="polite"` region in shell) — `Accent color set to {preset}.` |
| Toast | shell-managed `aria-live="polite"` toast region |

---

## 9. Sidebar nav

Settings becomes the **third nav item** in the sidebar (below Imports). See `../shell.md` for full nav block.

| Order | Label | Icon | Route | Active match |
|---|---|---|---|---|
| 1 | Dashboard | `bar-chart-2` | `/` | exact `/` |
| 2 | Imports | `file-text` | `/runs` | prefix `/runs` |
| 3 | Settings | `settings` | `/settings` | prefix `/settings` |

---

## 10. Shared components used

| Component | Used For | Spec |
|---|---|---|
| `PageHeader` | top of page | `../shared-components.md` |
| `AccentColorPicker` | new shared component | this page introduces it; spec lives here under § 4.C |
| `<Autocomplete>` (frappe-ui) | Default Company input | frappe-ui |
| `<Input>` / labels / helper-text patterns | from frappe-ui Tailwind primitives | n/a |
| `ConfirmDialog` | Discard prompt + navigate-away prompt | `../shared-components.md` |
| `Toast` | save success + error | `../shared-components.md` |
| `SkeletonBlock` | loading state | `../shared-components.md` |

---

## 11. DocType field requests *(approved 2026-05-24)*

Already approved and captured in arch decisions D13. Shipped by component **c013** (schema-additions).

| Status | Field | DocType | Type | Consumed by |
|---|---|---|---|---|
| Approved | `accent_color` | `Cashew Settings` | Select (`Indigo\nTeal\nBurnt Orange\nMonochrome\nCyan`, default `Indigo`) | This page (Appearance section) + shell theme propagation |
| Approved | `notes` | `Cashew Import Run` | Small Text | run-workspace (RunHeader + Upload section) |
| Approved | `validation_severity` | `Cashew Import Row` | Select (`Error\nWarning\nInfo`, default `Error`, `depends_on=eval:doc.validation_status=='Error'`) | run-workspace RowsWorkbench (filter facet + pill modifier) |
| Withdrawn | `row_note` | `Cashew Import Row` | — | Withdrawn — `Cashew Import Row.note` already exists; UI surfaces existing field |

---

## 12. Out of scope (explicit)

- Per-user theming. Accent is app-wide per D14.
- Editing Cashew Category Mapping / Cashew Account Mapping inside the SPA. Deep-link to Desk only.
- Global per-run defaults on Cashew Settings (default_customer / default_supplier / balance_adjustment_account / je_rounding_tolerance) — user direction 2026-05-24, no global fallbacks introduced.
- Custom hex picker. Presets only.
- Multi-language UX strings (page copy is English-only v1).
