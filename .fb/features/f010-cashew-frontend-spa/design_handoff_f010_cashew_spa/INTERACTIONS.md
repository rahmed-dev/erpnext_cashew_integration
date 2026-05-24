# Interactions & Behavior — Cashew SPA

Cross-component patterns. Reference for keyboard, hover, modal, realtime, error, and a11y behavior. Per-page details live in `spec/pages/*.md` — this file is the cross-cutting layer.

---

## Hover & focus

| Element | Hover | Focus-visible |
|---|---|---|
| `cs-btn` (any variant) | background tint or color shift (120ms) | 2px accent ring, 2px offset |
| Sidebar nav item | subtle dark fill (`#2a2a2a`) | accent ring |
| Table row | `var(--cs-bg-2)` fill + cursor pointer | row gets `aria-selected` styling |
| Import card (recent imports strip) | shadow lift (`var(--cs-shadow-md)`) + `translateY(-1px)` | accent ring |
| Chip / filter | `var(--cs-bg-2)` fill | accent ring |
| Kebab trigger | reveals on row hover (opacity 0 → 1); always visible on mobile | always visible when focused |
| Inline action icons in row | hidden by default, opacity 1 on row hover | always visible when focused |

**Rule:** color is never the only signal. Every hover state pairs with cursor or layout cue.

---

## Click & navigation

| Element | Action |
|---|---|
| Sidebar nav item | `router.push(route)` |
| App switcher → Back to Desk | hard nav to `/app` (window.location, exit SPA) |
| Run row (imports list) | `router.push('/runs/' + name)` |
| Recent import card | `router.push('/runs/' + name)` |
| Run header `<` back | `router.push('/runs')` |
| "+ New Import" | `router.push('/runs/new')` |
| "Open in Desk" link | `window.open('/app/cashew-import-run/' + name, '_blank')` |
| Status pill in table | non-interactive (informational); except: error pill → opens ValidationFixModal |
| Posted doc link in completed view | `window.open('/app/{doctype}/' + name, '_blank')` |

**Routing transitions on parse success** (D10.b):
After `parse_and_preview` returns, use `router.replace` (not `push`) from `/runs/new` to `/runs/:name`. This prevents back-button to a stale `/runs/new` state.

---

## Keyboard

### Global (shell-owned)

| Key | Behaviour |
|---|---|
| `Tab` / `Shift+Tab` | Standard focus traversal. All interactive controls must be reachable. |
| `Esc` | Close any open modal / dropdown / dialog. Cancel inline edit. |
| `/` (slash) — *optional, TD pick* | Focus the page's primary search input (Imports List or Workbench). |

### Workbench inline party edit (`InlinePartyEdit.vue`)

| Key | Behaviour |
|---|---|
| `Tab` | Move between Party Type select and Party autocomplete |
| `Enter` | Save (calls `row_explorer_set_party`); cell shows spinner; row updates |
| `Esc` | Cancel without saving; cell reverts |

### Workbench bulk select

| Key | Behaviour |
|---|---|
| `Shift+Click` on row checkbox | Range select from last-checked to current |
| `Cmd/Ctrl+A` while focus is in the table | Select all visible rows (filtered set) |
| `Esc` while a selection exists | Clear selection |

### Modals (`ConfirmDialog`, `ValidationFixModal`, `BulkPartyModal`)

| Key | Behaviour |
|---|---|
| `Tab` | Focus-trapped within modal |
| `Esc` | Cancel (equivalent to clicking Cancel or outside) |
| `Enter` | Confirm primary action (when focus is on confirm button or not in a multi-line input) |

### Split workbench drawer (alternate layout)

| Key | Behaviour |
|---|---|
| `↑` / `↓` while drawer focused | Move selection to previous / next row in the visible list |
| `Esc` while drawer focused | Collapse drawer |
| `Enter` while focus is in party autocomplete | Save & next (advance selection by 1) |

---

## Form patterns

### Inline edit (party cell)

1. User double-clicks Party cell.
2. Cell renders Party Type select (90px) + Party autocomplete (flex 1) + check button.
3. User picks type → autocomplete `reference_doctype` flips dynamically (D5 rule 2 means the autocomplete re-queries with the right `search_link` route).
4. Enter → spinner on the check icon → `row_explorer_set_party` → on success, cell renders the new value; if `validation_status` flipped, row pill updates.
5. Esc / click outside → revert without saving.

### Validation fix modal (per error code)

Conditional field set, all reusing frappe-ui primitives:

| `validation_error_code` | Fields shown |
|---|---|
| `NO_ACCOUNT_MAP` | `resolved_account` (Autocomplete → Account) |
| `MISSING_PARTY` | `resolved_party_type` (Select Customer/Supplier) + `resolved_party` (Autocomplete, dynamic ref) |
| `NO_EXTERNAL_ACCT` | `resolved_external_account` (Autocomplete → Account) |
| *(future codes)* | TD adds more cases here |

Save button label: **"Save & re-validate"**. On success: modal closes if row becomes `Valid`; otherwise stays open showing the new error (could be a cascading one).

### Bulk party modal

Same Party Type + Party fields, applied to N selected rows. Hint text: *"Existing party values on selected rows will be overwritten."* On save, toast: `"Set party 'ACME Pvt Ltd' on 8 rows"`.

### CSV dropzone (Upload section)

- Drag-over: dashed border turns accent color, background tints `var(--cs-accent-50)`.
- Drag-leave: revert.
- Drop / click: file picker.
- Selected file: replace dropzone content with file row (icon chip + name + size + remove ×).
- Click "Parse →" → button shows spinner; dropzone disables.
- Failure: inline red error below dropzone (in addition to shell toast).

---

## Realtime updates (D8)

### Subscriptions

| Page | Subscription | Effect |
|---|---|---|
| Finance Dashboard | `Cashew Import Run` `doc_update` (list-level) | Debounced (2s) re-fetch of `dashboard_summary` |
| Imports List | `Cashew Import Run` `doc_update` (list-level) | Update matching row in place (status pill, counters, "Updated" timestamp). New runs appear at top with a 500ms border-highlight pulse. |
| Run Workspace | `Cashew Import Run` `doc_update` scoped to current run | `status` change drives section swap; counters update; per-row fields update in place (`validation_status`, `posted_doctype`, `posted_docname`, `revert_status`). |

### Connection state UI

The sidebar `RealtimeStatusIndicator` renders 4 states (see `DESIGN_TOKENS.md` § color § functional). On permanent socket loss, the indicator flips to "Polling" and a polling loop (`get_run_progress(run_name)` every 30s) takes over for any subscribed run.

### Live row updates (workbench in Processing state)

- Row's `posted_docname` field comes in via `doc_update`.
- Row's left-border animates from transparent → green over 200ms.
- "Posted As" cell renders the doc link.
- Counters in `RunHeader` and the progress banner tick up.

### Don't redirect on status change

A status change updates the section rendered on the same URL — never `router.push` away. The header's `<` back button is the only way to leave a run mid-flight.

---

## Loading states

Three patterns, applied consistently:

### 1. Initial page load (skeleton)

On mount, before first data resolves:
- Tiles render as `SkeletonBlock`s with the label visible and the amount shimmering.
- Tables render 5–6 skeleton rows of plausible cell widths.
- Charts render a circular shimmer or empty axes.

Don't render a centered "Loading…" spinner — operators perceive skeletons as faster.

### 2. Filter / sort change

Don't unmount the table. Add a 20–30% opacity overlay + shimmer for ~200ms while the new data arrives. Header and filters stay interactive.

### 3. Action in flight

A button that triggers an API call:
- Disables (`opacity: 0.6`, `cursor: not-allowed`)
- Renders an inline spinner before the label
- Label may swap to gerund: "Parse →" becomes "Parsing…"
- On success: revert to default (the section swap usually replaces the button anyway).
- On failure: button re-enables; shell toast appears.

---

## Error states

### Per-page errors

When `dashboard_summary` fails or `frappe.client.get_list` errors:
- Section content area replaced by a centered card: *"Could not load {thing}"* + retry button.
- Shell also fires a toast (D5.c).

### Per-row errors (workbench)

- Row's left-border red.
- `validation_status` pill in Status column shows Error.
- `Error / Resolved Account` column shows the truncated message in red text; full message on hover tooltip.
- Per-row kebab includes "Fix this row…" → opens ValidationFixModal.

### Network / 403

ShellErrorToastBoundary intercepts every `/api/*` error:
- `403` → toast title "Permission denied"; body = server message; no retry button.
- `5xx` → toast with title "Something went wrong"; body = server message; retry button if the action was idempotent.
- Network failure → toast "Offline"; retry on its own when connection returns.

Toasts:
- Stack bottom-right.
- Auto-dismiss 5s.
- Click to dismiss.
- `aria-live="polite"`.

---

## Empty states

| Surface | When | Content |
|---|---|---|
| Finance Dashboard | All totals are 0 + no recent runs | Centered illustration + "Nothing to show for this period." + body + "Start an Import" primary + "Change period" secondary. |
| Imports List | `get_count('Cashew Import Run') == 0` | Centered illustration + "No imports yet." + "Start an Import" primary + "Configure mappings →" secondary (links back to Desk). |
| Imports List (filters return zero) | `get_count` > 0 but filtered list empty | Inline "No runs match these filters." + Clear filters button. |
| Run Workspace — Preview | parse returned 0 rows (defensive) | Inline "This run has no rows. Re-parse the CSV." |
| Run Workspace — Workbench | (defensive — shouldn't happen) | Same. |

---

## Animations & timing

| Animation | Duration | Easing |
|---|---|---|
| Status pill pulse (Processing / Reverting) | 1.4s | ease-in-out, infinite, opacity 1 ↔ 0.55 |
| Skeleton shimmer | 1.5s | linear, infinite |
| Hover color/background change | 120ms | linear |
| Card hover lift | 150ms | ease |
| Sidebar collapse/expand | 180ms | ease |
| Drawer collapse (split workbench alt) | 200ms | ease |
| Dropdown / popover appear | 120ms | ease-out |
| Selection footer slide-up | 200ms | ease-out, `transform: translateY(100%) → 0` |
| Realtime row pulse | 500ms one-shot | ease-out, border-highlight |
| Status pill color transition (after action success) | 200ms | ease |

Reduced-motion: respect `@media (prefers-reduced-motion: reduce)` — disable shimmer and pulse, replace transitions with instant changes.

---

## Responsive behavior (cross-page rules)

### Sidebar
- ≥1024px: 224px expanded.
- 640–1023px: 200px expanded.
- <640px: hidden by default. Hamburger button top-left of content opens an overlay drawer (slide-in from left, 200ms).

### Tables
- Tables generally drop low-priority columns at narrower widths (per-page rules in spec).
- At <640px, list-style tables (Imports List, Workbench RowsTable) switch to **card lists**: one card per row, key fields stacked. Workbench bulk select via tap-and-hold instead of checkbox.

### Toolbars
- Filter dropdown collapses into a single "Filters" button at <768px → opens a bottom-sheet on tap.

### Modals
- Desktop: centered, max 480–640px wide.
- Mobile (<640px): full-screen sheet sliding up from bottom.

---

## Accessibility

| Concern | Pattern |
|---|---|
| Heading order | Each page has one `<h1>` (PageHeader title). Sections use `<h2>` / `<h3>`. |
| Landmarks | `<nav>` for sidebar, `<main>` for content, `<aside>` for drawers |
| Status pills | text label + colored bg + `aria-label="{kind}: {value}"` (never color alone) |
| Charts | always paired with a screen-reader-only text summary (e.g. *"Income Rs 4,245,000, Expense Rs 2,867,350, Net Rs 1,377,650 surplus, May 2026"*) |
| Tables | semantic `<table>` + `<thead>` + `aria-sort` on sorted column header |
| Sortable headers | `aria-sort="ascending"` / `"descending"` / `"none"` |
| Modal | `role="dialog"` + `aria-modal="true"` + focus trap + return focus to trigger on close |
| Dropdowns / popovers | `aria-haspopup="menu"` + `aria-expanded` on trigger; `role="menu"` + `role="menuitem"` on items |
| Toast region | `aria-live="polite"` |
| Selection checkbox | `aria-label="Select row {row_idx}"` |
| Skeletons | `aria-busy="true"` on the loading region |
| Action buttons in flight | `aria-busy="true"` + descriptive label change ("Parsing…") |

---

## State management notes (D6)

**No `localStorage` / `sessionStorage` for view state.** This is binding.

What this means in practice:
- Filter selections, period selections, sort, pagination, column show/hide, drawer open/closed — all live in component state or pinia store, **wiped on page reload**.
- URL params are fine for *route-bound* state (e.g. `?status=Failed` if TD wants deep-linkable filters; but this is a deliberate decision, not auto).
- User preferences (favorite filters, saved presets) are deferred — D6 says no v1.

---

## When in doubt

| Question | Answer |
|---|---|
| Should this update via socket or polling? | Both — wire socket, the realtime composable falls back to polling automatically. |
| Should this action have a confirm dialog? | If it mutates GL data (Queue, Revert) or deletes a record (Discard) — yes, always. If it's idempotent + reversible (Re-validate, Re-parse) — no. |
| Should this state persist across page reload? | No (D6). |
| Should this column be visible by default? | Check `spec/pages/run-workspace.md` § 5.III.3 — there's a "hidden by default" flag. |
| Should this Link selector use frappe-ui Autocomplete? | Yes — always (D5 rule 2). |
| Where do I add a new bulk action? | The `workbench/registries/actions.js` declarative registry (D11). |
| Where do I add a new filter facet? | The `workbench/registries/filters.js` declarative registry (D11). |
