# Handoff — f010 Cashew Frontend SPA

This bundle is the design handoff for **f010-cashew-frontend-spa**: a Vue 3 SPA, served at `/cashew` inside the `cashew_integration` Frappe app (Doppio pattern, identical shape to Frappe CRM and Helpdesk).

Three surfaces in scope: **Finance Dashboard**, **Imports List**, **Run Workspace**.

---

## About these files

The files in `design-reference/` are **prototypes built in HTML + React** for visual review. They are **not production code** — do not import them, do not copy them line-for-line. Your task is to **recreate them in the real codebase** (Vue 3 + frappe-ui + Tailwind, per `spec/arch-decisions.md` D1–D2), reusing the codebase's existing patterns.

The files in `spec/` are the **authoritative behavioural / data spec** — copied verbatim from `.fb/` in the repo. If the HTML prototype contradicts the spec, **the spec wins**. The prototype is for visuals + interaction feel only.

Both are needed:
- `spec/` answers: *what does this component do, what fields, what API, what states*
- `design-reference/` answers: *what does it look like, what's the spacing/color rhythm, how do interactions feel*

---

## Fidelity

**High-fidelity.** Pixel-perfect mockups with final colors, typography, spacing, status pill palette, and interaction patterns. Recreate the UI pixel-perfectly using the codebase's existing libraries (frappe-ui primitives + Tailwind utility classes), not by copying our inline-style React JSX.

Where the prototype uses inline styles or hand-rolled components, the production build should use the equivalent **frappe-ui** primitive (Button, Input, Autocomplete, Dropdown, Dialog, Tooltip) and **Tailwind** classes against the design tokens in [`DESIGN_TOKENS.md`](./DESIGN_TOKENS.md).

---

## Stack & architecture (binding)

From `spec/arch-decisions.md` and `spec/feature.yaml` — every decision below is binding unless an Architect decision record changes it.

| Concern | Decision |
|---|---|
| **Hosting** | Doppio `www/` pattern. `/cashew/<path:app_path>` catch-all → `cashew_integration/www/cashew.html` → Vue Router (HTML5 history) takes over client-side. |
| **Entry** | `cashew_integration/www/cashew.py` does perm check + boot dict injection (csrf_token, session_user, sysdefaults, default_company, default_currency). |
| **Auth** | Same-origin Frappe session cookie + CSRF from `window.boot.csrf_token`. **No API keys in `localStorage`.** |
| **Role gate** | `System Manager` OR `Accounts Manager`. Server-side check in `cashew.py`. |
| **Build** | `bench build --app cashew_integration` → Doppio `build.json` hook → `yarn build` in `frontend/`. Commit the tiny `www/cashew.html` shell; gitignore `public/frontend/` and `frontend/node_modules`. |
| **Routes** | `/` → Finance Dashboard · `/runs` → Imports List · `/runs/new` and `/runs/:run_name` → Run Workspace. |
| **State** | TD-decided (Pinia or composables). **Session-only view state — no `localStorage` / `sessionStorage` persistence of filters/presets/period.** |
| **Realtime** | Socket.IO; subscribe to `Cashew Import Run` `doc_update`. Fall back to 30s polling on permanent socket loss. |
| **PWA** | `vite-plugin-pwa` stays on. Future-proofing for installable surface; not used for offline work in v1. |

### The 4 binding API rules (D5 — read this carefully)

1. **Reads → `frappe.client.*`.** Use `frappe.client.get_list`, `get_doc`, `get_count`. **Never** wrap a read in a custom whitelisted endpoint — Frappe applies DocPerm + User Permissions + If-Owner + field-level perms automatically.
2. **Link selectors → `frappe-ui <Autocomplete>` with `reference_doctype` + `reference_fieldname`.** Routes through `frappe.desk.search.search_link`, which honors any `get_query` registered for that field. **Same code path the Desk form uses.**
3. **Writes / multi-step actions → reuse `cashew_integration/api.py` whitelisted methods.** Every method MUST call `frappe.has_permission(doctype, ptype, doc=...)` at entry.
4. **Aggregates → one purpose-built custom endpoint per surface** (e.g. `dashboard_summary`). Internally use `frappe.get_all(... ignore_permissions=False)` so row-level perms still apply during aggregation.

These mirror how Frappe CRM and Helpdesk are built. Deviation requires an Architect decision record.

---

## Surfaces — what each prototype covers

| Surface | Spec | Prototype artboard(s) |
|---|---|---|
| **App Shell** (sidebar, app-switcher, user chip, realtime indicator) | `spec/shell.md` | Wraps every page in the prototype. See `design-reference/src/Shell.jsx`. |
| **Finance Dashboard** | `spec/pages/finance-dashboard.md` | `Dashboard · 01 Loaded` / `02 Loading` / `03 Empty` |
| **Imports List** | `spec/pages/imports-list.md` | `Imports List · 01 Loaded` / `02 Loading` / `03 Empty` |
| **Run Workspace** (4 state-driven sections) | `spec/pages/run-workspace.md` | `Workspace · 01 Draft/Upload` → `02 Parsed/Preview` → `03 Validated · errors` → `04 Processing · live` → `05 Completed` → `06 Reverted` |
| **Shared components** | `spec/shared-components.md` | `Foundations` (color, type, status pills, buttons, tiles) |
| **Mobile** | each page's "responsive" section in the spec | `Mobile` row in the canvas (380 × 760) |
| **Alternates** *(exploratory)* | not in spec | `Alt · Single-bar dashboard` and `Alt · Split workbench` — opinionated proposals beyond spec. Treat as discussion material, not the deliverable. |

---

## How to open the prototype

The HTML prototype is a single self-contained file with a design canvas. Open `design-reference/Cashew SPA.html` in any modern browser:

- **Scroll / pan** the canvas to find an artboard
- **Click the expand button** on any artboard header → fullscreen focus mode (←/→ to step, Esc to close)
- **Tweaks panel** (bottom-right): live-adjust accent color, chart style, density (compact/comfortable), sidebar (expanded/collapsed), theme (warm/cool), roundness (sharp/regular/round/extra). Use it to see the spectrum of tokens the system supports.

**Interactions that actually work in the prototype** (useful for behavioural reference):
- Imports List status filter is a real multi-select; clears via active chips
- Workspace inline party edit (double-click any Party cell; Enter saves, Esc cancels)
- Workspace bulk select + bulk modal
- Validation-fix modal renders the right field per `validation_error_code`
- "Queue Import" → confirm modal → state flips to Processing → rows mark posted live ~every 1.2s → Completed
- Split-workbench alternate: collapse/expand right drawer, prev/next row chevrons, edge-rail handle when collapsed

---

## Quick implementation order

A suggested sequence — the architecture spec lays out dependencies (c001–c011), this is the UI build order against those components:

1. **`c001` scaffold + `c002` host route + `c003` build hook** — get a "Hello Cashew" Vue page rendering at `/cashew` end-to-end. No designs yet; just the Doppio plumbing.
2. **`c004` shell** — sidebar, app switcher, user chip, routing skeleton, mobile collapse. Three routes resolve to placeholder pages.
3. **Shared components from `spec/shared-components.md`** — `StatusPill`, `AmountDisplay`, `PageHeader`, `EmptyState`, `SkeletonBlock`, `ConfirmDialog`, `DateRange`, `KebabMenu`. Get these stable before page work; every page consumes them.
4. **`c005` Imports List** — straightforward CRUD list, exercises `frappe.client.get_list` (D5 rule 1).
5. **`c009` `dashboard_summary` endpoint** + **`c007` Finance Dashboard** — first aggregate endpoint; first chart.
6. **`c006` Run Workspace** — the largest component. Build section by section: Upload → Preview → RowsWorkbench → CompletedSummary.
7. **`c008` realtime client** — Socket.IO bootstrap; wire `doc_update` subscription into Imports List + Run Workspace.
8. **`c010` API permission audit** + **`c011` realtime emission audit** — refactor passes; can run in parallel late in the cycle.

---

## What's intentionally NOT in this bundle

The spec explicitly defers these. Don't build them, don't link to them from the SPA:

- **f006 Row Explorer** (`/app/cashew-row-explorer/<run>`) — the Frappe Page is untouched by f010 (D7). SPA Run Workspace owns row-level UX natively.
- **Cashew Settings / Mapping screens** — stay on Desk for v1 (`/app/cashew-settings`, `/app/cashew-category-mapping`, `/app/cashew-account-mapping`). Out of scope.
- **Per-page role-based route hiding** — D5.c shell-level graceful 403 toast only.
- **Saved filter/period presets** (D6 — session only).
- **CSV/Excel export of the imports list.**
- **Inline edits to parsed row data other than party fields.**
- **Comments / discussions / attachments on a run.**

---

## Files in this bundle

```
design_handoff_f010_cashew_spa/
├── README.md                    ← this file
├── DESIGN_TOKENS.md             ← every color/radius/type value
├── COMPONENT_MAPPING.md         ← prototype component → Vue SFC mapping
├── INTERACTIONS.md              ← keyboard, hover, modal, realtime patterns
├── design-reference/            ← THE PROTOTYPE — visual reference, do not ship
│   ├── Cashew SPA.html
│   ├── design-canvas.jsx        ← canvas chrome (not part of the design)
│   ├── tweaks-panel.jsx         ← tweaks panel chrome (not part of the design)
│   └── src/
│       ├── data.jsx             ← mock PKR data; use as field-shape reference
│       ├── ui.jsx               ← StatusPill, AmountDisplay, Tile, EmptyState, Icon set
│       ├── Shell.jsx            ← sidebar + app switcher + user chip
│       ├── Dashboard.jsx        ← Finance Dashboard
│       ├── ImportsList.jsx      ← Imports List
│       ├── Workspace.jsx        ← Run Workspace (all 4 states)
│       ├── Foundations.jsx      ← design system artboard
│       └── Alternates.jsx       ← exploratory alternate layouts
└── spec/                        ← AUTHORITATIVE — copied from .fb/
    ├── feature.yaml
    ├── arch-decisions.md        ← D1–D11 + UI-phase flags
    ├── ui-index.yaml            ← page inventory
    ├── shell.md
    ├── shared-components.md
    └── pages/
        ├── finance-dashboard.md
        ├── imports-list.md
        └── run-workspace.md
```

---

## When in doubt

- **Behavioural question** (what does this control do? what API does it call?) → `spec/` is the answer.
- **Visual question** (what's the spacing? what's the exact pill color? what does hover look like?) → `design-reference/` is the answer.
- **Both contradict** → spec wins. File a question back to the design / architect agent.

---

## Related app conventions

The repo's `CLAUDE.md` codifies these — they apply to all future SPA work, not just f010:

- The four API rules above.
- SPA hosting (Doppio `www/` pattern).
- Other surfaces (Desk forms + `cashew-row-explorer` Frappe Page) are intentionally untouched by the SPA build.
