# Shared Components — Cashew SPA

Components referenced on multiple pages of the Cashew SPA. Implement once, import everywhere. This document is the single source of truth for the design tool — every page brief references components by name; the spec lives here.

> All components are Vue 3 SFCs under `frontend/src/components/shared/`. Frappe-ui primitives where possible; pure Tailwind otherwise. No external icon set besides `lucide-vue-next` (already pulled in via vite plugin per D2).

---

## 1. `StatusPill`

A colored pill rendering a status value. Used everywhere a Cashew enum needs to be visualized.

### Used on
- `finance-dashboard.md` — RecentImportsStrip card status
- `imports-list.md` — Status column in the runs table; row card variant
- `run-workspace.md` — RunHeader status; row `validation_status`; per-row `revert_status`; `txn_type` (with a `subdued` variant)

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `kind` | `"run-status" \| "row-validation" \| "row-revert" \| "txn-type"` | yes | Determines which enum table to use |
| `value` | string | yes | The actual enum value (e.g. `"Completed"`, `"Error"`, `"Income"`) |
| `size` | `"sm" \| "md"` | no — default `"md"` | sm used in dense tables; md elsewhere |
| `pulse` | boolean | no — default `false` | when `true`, applies a subtle pulsing animation (use for `Processing`, `Reverting`) |

### Enum tables

**`kind="run-status"`** — every value of `Cashew Import Run.status`:
| Value | Label | Color (Tailwind hint) |
|---|---|---|
| `Draft` | Draft | gray-300 bg, gray-700 text |
| `Parsed` | Parsed | sky-100 bg, sky-700 text |
| `Validated` | Validated | blue-100 bg, blue-700 text |
| `Queued` | Queued | indigo-100 bg, indigo-700 text |
| `Processing` | Processing | indigo-100 bg, indigo-700 text, **pulse** |
| `Completed` | Completed | green-100 bg, green-700 text |
| `Failed` | Failed | red-100 bg, red-700 text |
| `Cancelled` | Cancelled | gray-200 bg, gray-700 text |
| `Reverting` | Reverting | amber-100 bg, amber-800 text, **pulse** |
| `Reverted` | Reverted | amber-100 bg, amber-800 text |
| `Revert-Failed` | Revert Failed | red-100 bg, red-800 text |

**`kind="row-validation"`** — `Cashew Import Row.validation_status`:
| Value | Label | Color |
|---|---|---|
| `Valid` | Valid | green-100 bg, green-700 text |
| `Error` | Error | red-100 bg, red-700 text |
| `Skipped` | Skipped | gray-200 bg, gray-700 text |

**`kind="row-revert"`** — `Cashew Import Row.revert_status`:
| Value | Label | Color |
|---|---|---|
| *(empty)* | (not rendered) | — |
| `Reverted` | Reverted | amber-100 bg, amber-800 text |
| `Revert-Failed` | Revert Failed | red-100 bg, red-800 text |

**`kind="txn-type"`** — `Cashew Import Row.txn_type`:
| Value | Label | Color |
|---|---|---|
| `Income` | Income | green-50 bg, green-700 text |
| `Expense` | Expense | red-50 bg, red-700 text |
| `Transfer` | Transfer | slate-100 bg, slate-700 text |
| `External Transfer` | External Transfer | slate-100 bg, slate-700 text |
| `Adjustment` | Adjustment | yellow-50 bg, yellow-800 text |
| `Loan Receivable` | Loan Receivable | violet-100 bg, violet-700 text |
| `Loan Payable` | Loan Payable | violet-100 bg, violet-700 text |

### Visual rules
- Pill shape: rounded-full, horizontal padding 8px (sm) or 10px (md)
- Font: 12px (sm) or 13px (md), medium weight
- Icon (optional, inside pill, lucide): `check` for Valid/Completed, `x` for Error/Failed/Revert-Failed, `clock` for Queued, `loader-2` (spinning) for Processing/Reverting, etc.
- `pulse` adds a soft 2-step opacity animation (1.0 ↔ 0.65), 1.4s duration, indefinite

### Accessibility
- Always renders the value as text — color is never the only signal
- `aria-label` includes the `kind` and `value` (e.g. `"Run status: Completed"`)

---

## 2. `AmountDisplay`

Formatted currency display, used wherever a money value renders.

### Used on
- `finance-dashboard.md` — BalanceTileGrid amounts, chart center label, category list amounts
- `imports-list.md` — *(none directly; amounts not shown on list)*
- `run-workspace.md` — Amount + Source Amt columns; counts grid; result banner

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `amount` | number \| null | yes | The number. `null` renders as `—` |
| `currency` | string | yes | ISO code, e.g. `"INR"`, `"USD"` — used for symbol + locale |
| `signed` | boolean | no — default `false` | When true, show `+` / `−` prefix and color (green/red) |
| `sign-source` | string | no | If signed, pass the `income_flag` or `txn_type` to determine direction |
| `compact` | boolean | no — default `false` | When true, use locale compact ("₹1.2L", "$1.2K") |
| `tabular` | boolean | no — default `true` | Apply `tabular-nums` for column alignment |

### Format rules
- Symbol position per locale (Indian rupee: `₹ 1,24,500.00`, USD: `$124,500.00`)
- Decimals: 2 by default; respect Frappe's `Currency` precision if available
- `null` or missing amount → `—` (em-dash), muted color
- Use the browser's `Intl.NumberFormat` for actual formatting; pass currency code

---

## 3. `PageHeader`

Title row at the top of any page. Used on every page.

### Used on
- `finance-dashboard.md` — section A
- `imports-list.md` — section A
- `run-workspace.md` — `RunHeader` is a richer variant (uses `PageHeader` as its base then layers run metadata on top)

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | h1 text |
| `subtitle` | string \| null | no | small muted text below title |
| `back-route` | string \| null | no | when set, renders a `<` chevron at the very left that routes there |

### Slots
| Slot | Purpose |
|---|---|
| `meta` | optional content between title and actions (e.g. run period + counts on RunHeader) |
| `actions` | right-aligned action buttons / dropdowns |

### Visual rules
- Title is h1, ~24–28px, semibold
- Subtitle: 13px muted
- Single row on desktop; wraps on mobile (actions move below title)
- Bottom border line by default; can be turned off via prop if not needed

---

## 4. `EmptyState`

Centered "nothing here yet" placeholder. Renders an illustration, title, body, primary CTA, optional secondary action.

### Used on
- `finance-dashboard.md` — DashboardEmptyState (specialization)
- `imports-list.md` — section E (no imports yet)
- `run-workspace.md` — empty-preview / empty-workbench edge cases

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `illustration` | `"empty-list" \| "no-data" \| "empty-results" \| "first-run"` | no — default `"no-data"` | Picks a built-in line-art SVG |
| `title` | string | yes | Headline (sentence case, end with period) |
| `body` | string | no | One or two sentences of explanation |
| `primary` | `{ label: string, action: () => void \| string }` | no | The main CTA; `action` is either a function or a route string |
| `secondary` | `{ label: string, action: () => void \| string }` | no | Secondary link/button below the primary |

### Visual rules
- Centered horizontally and vertically inside its container
- Illustration ~120–180px tall, line-art style, muted color
- Title 18–20px semibold
- Body 14px muted text, max 60ch
- Primary is a solid button; secondary is a text link

---

## 5. `SkeletonBlock`

Animated placeholder for loading content. Used wherever a real component would render once data arrives.

### Used on
- All pages — initial loading states

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `shape` | `"line" \| "block" \| "circle" \| "row"` | no — default `"line"` | shape preset |
| `width` | string | no | CSS width (e.g. `"60%"`, `"120px"`) |
| `height` | string | no | CSS height |
| `lines` | number | no — default `1` | for `shape="line"`, how many stacked lines |

### Visual rules
- Subtle 2-tone shimmer animation, 1.5s loop
- Default color: gray-200 base, gray-100 highlight
- Should not be visually loud — operator should be able to scan past it

---

## 6. `ConfirmDialog`

Modal confirmation dialog for destructive or expensive actions. Used wherever a click should require explicit "yes I mean it".

### Used on
- `run-workspace.md` — Queue confirm, Cancel confirm, Revert confirm, Discard confirm
- `imports-list.md` — Revert / Cancel via row-action menu

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `open` | boolean | yes | v-model |
| `kind` | `"info" \| "warning" \| "danger"` | no — default `"warning"` | drives icon + accent color |
| `title` | string | yes | e.g. "Revert this import?" |
| `body` | string | yes | one or two sentences |
| `confirm-label` | string | no — default `"Confirm"` | e.g. "Revert" |
| `cancel-label` | string | no — default `"Cancel"` |  |
| `confirming` | boolean | no — default `false` | when true, confirm button shows spinner + is disabled |

### Events
- `confirm` — user clicked confirm
- `cancel` — user clicked cancel / pressed Esc / clicked outside

### Visual rules
- `danger` kind: red accent, danger-style confirm button (red background)
- `warning`: amber accent
- `info`: blue accent
- Always focus-trapped; Esc cancels; clicking outside cancels

---

## 7. `DateRange`

Read-only date-range display + optional editable picker. Used everywhere a `period_start`/`period_end` pair shows up.

### Used on
- `finance-dashboard.md` — PeriodSelector (custom range mode)
- `imports-list.md` — FilterBar PeriodFilter (custom range mode)
- `run-workspace.md` — Run header period display

### Display props (read-only mode)
| Prop | Type | Required | Notes |
|---|---|---|---|
| `start` | string `YYYY-MM-DD` \| null | yes | |
| `end` | string `YYYY-MM-DD` \| null | yes | |
| `format` | `"short" \| "long"` | no — default `"short"` | short = `"Apr 1 – Apr 30, 2026"`; long = `"April 1, 2026 – April 30, 2026"` |
| `null-text` | string | no — default `"—"` | rendered when both null |

### Editable mode (picker)
A separate variant `DateRangePicker` (same component, `editable` prop) renders two calendar pickers side-by-side. Emits `update:start`, `update:end`.

---

## 8. `RealtimeStatusIndicator`

Shell-level component showing Socket.IO connection state. Lives at the bottom of the sidebar.

### Used on
- `shell.md` — sidebar bottom

### Props
None (reads from a global realtime store/composable).

### States
See `shell.md` section 4 for the state table (Connected / Reconnecting / Polling / Disconnected).

---

## 9. `KebabMenu`

Generic three-dots menu trigger + dropdown. Used wherever a row or card has overflow actions.

### Used on
- `imports-list.md` — row action menu
- `run-workspace.md` — per-row actions in RowsTable

### Props
| Prop | Type | Required | Notes |
|---|---|---|---|
| `items` | `MenuItem[]` | yes | array of `{ label, icon?, action: () => void \| string, disabled?: boolean, danger?: boolean, divider?: boolean }` |
| `align` | `"left" \| "right"` | no — default `"right"` | which edge to align dropdown to |

### Visual rules
- Trigger: `more-vertical` lucide icon, 16–18px, button-style hit area
- Dropdown: white card, soft shadow, 4–6px radius
- `danger` items render in red text
- Keyboard: ↑↓ navigate, Enter selects, Esc closes

---

## 10. `Toast` & `ToastQueue` *(shell-owned; documented for reference)*

Lives in `shell.md` (section "ErrorToastBoundary"). Pages don't import this directly — they emit toast events via a global `useToast()` composable. Documented here so the design tool knows the visual treatment.

| Variant | Icon | Accent | When |
|---|---|---|---|
| `success` | `check-circle` | green | "Set party on 8 rows" |
| `info` | `info` | blue | informational |
| `warning` | `alert-triangle` | amber | non-fatal issue |
| `error` | `alert-circle` | red | API failures (D5.c), 403s, network errors |

Position: fixed bottom-right; stacked; auto-dismiss after 5s; click-to-dismiss; show in `aria-live="polite"` region.

---

## 11. `frappe-ui` primitives used directly (no wrapper)

These are imported from `frappe-ui` directly and used as-is. Listed here so Designer knows they're not custom.

| Primitive | Used for |
|---|---|
| `<Autocomplete>` | every Link selector (Company, Customer, Supplier, Account) — D5 rule 2 |
| `<Button>` | every button (primary / secondary / danger / link variants) |
| `<Input>` | text inputs (search, custom amount, etc.) |
| `<Select>` | enum selects when not styled as a pill or dropdown chip |
| `<Tooltip>` | column header tooltips, truncated text expansion |
| `<Dialog>` | wrapper used by `ConfirmDialog`, `ValidationFixModal`, `BulkPartyModal` |
| `<Dropdown>` | wrapper used by `KebabMenu`, app switcher, user chip, filter chips |

---

## 12. Component file layout (for TD)

Strawman — TD finalizes during component spec:

```
frontend/src/components/shared/
  StatusPill.vue
  AmountDisplay.vue
  PageHeader.vue
  EmptyState.vue
  SkeletonBlock.vue
  ConfirmDialog.vue
  DateRange.vue
  DateRangePicker.vue
  KebabMenu.vue
  (Toast/ToastQueue live under shared/toast/)
```

Plus icons SVGs (illustration set for `EmptyState`) under `frontend/src/components/shared/illustrations/`.

---

## 13. Designer notes (Claude Design)

- These components should feel like a coherent system — same corner radii, same spacing scale, same icon weight throughout.
- Lean on Tailwind's default scale where possible — don't invent new spacing tokens.
- Status colors are functional, not branded — they should look the same on any page that uses them. Don't redesign per page.
- All loading skeletons should use the same shimmer animation — different visual on different pages = noise.
- Icon set is `lucide` — pick consistent icons across pages (don't mix `info-circle` here and `help-circle` there for the same concept).
