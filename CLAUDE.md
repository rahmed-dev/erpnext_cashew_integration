# cashew_integration — Claude conventions

Per-app instructions for any future Claude session in this app.

## Source of truth: `.fb/`

This app is managed under the BMad Frappe Builder pipeline. Authoritative state:
- `.fb/system-arch/` — system-wide architecture decisions
- `.fb/features/{fid}-{name}/` — per-feature decisions, specs, reviews
- `.fb/features/index.yaml` — feature registry
- `.fb/pipeline.yaml` — current pipeline stage / handoff

Always check `.fb/` before making architectural assumptions.

## Live-site REST access (for debugging / verifying imports)

The production site is **`https://erp.nstack.xyz`**. API credentials for user
`ai@nstackhq.com` live at **`.secrets/erp-api.env`** (mode 600), gitignored via the
`.secrets/` rule in `.gitignore`. A mirror copy is at `~/.config/nstack/erp-api.env`.
Format: `ERP_URL`, `ERP_API_KEY`, `ERP_API_SECRET`.

Use it to verify what an import actually posted — read the Journal Entries and GL
Entries back and reconcile them against `Cashew Import Run` / `Cashew Import Row`,
rather than trusting the run's own counters.

```
Authorization: token <ERP_API_KEY>:<ERP_API_SECRET>
```

Three things that will waste time otherwise:

1. **Cloudflare blocks Python's `urllib`** on this host with `error 1010` (403,
   fingerprint-based) regardless of a valid token. Shell out to `curl` instead — same
   request, same headers, works.
2. **The request line caps at 4094 bytes** (gunicorn). A `["name", "in", [...]]` filter
   with a few hundred document names exceeds it and returns an HTML `Bad Request` page,
   not JSON. Chunk `in` filters to ~40 values per call.
3. **`frappe.client.get_list` returns `[]` on a permission failure**, not an error — an
   empty result silently reads as "clean". Sanity-check with
   `frappe.client.get_count` on each doctype before concluding anything from an
   empty list.

Child tables need `parent` and `parenttype` in the `get_list` params:
`{doctype: "Cashew Import Row", parent: "Cashew Import Run",
parenttype: "Cashew Import Run", filters: [["parent", "=", run]]}`.

**Never commit these values, never echo them into a file inside the repo other than
`.secrets/`, and never paste them into a commit message, log, or issue.** The repo has
a live GitHub remote — a `git add -f` would publish them.

Standing findings from the 2026-08-07 verification pass:
**`.fb/system-arch/import-integrity-2026-08-07.md`**.

## SPA API discipline (introduced for f010, applies to all future SPA work)

The Vue SPA (`/cashew`, see `f010-cashew-frontend-spa`) follows a hybrid API model that
preserves Frappe's role permission system and Link field query filters with zero
re-implementation. This is binding. Deviate only with an Architect decision record.

**Four rules:**

1. **Reads → `frappe.client.*`.** Use `frappe.client.get_list`, `frappe.client.get`
   (full doc incl. child tables — note: `frappe.client.get_doc` does NOT exist),
   `frappe.client.get_count` from the SPA. Never wrap a read in a custom whitelisted
   endpoint. Frappe applies DocPerm + User Permissions + If-Owner + field-level perms
   automatically through these handlers — re-implementing them in a custom endpoint
   risks drift.

2. **Link selectors → the shared `<LinkField>` wrapper**
   (`src/components/shared/LinkField.vue`). frappe-ui `<Autocomplete>` does NOT
   self-fetch — it only client-filters the `:options` array you hand it; a
   `reference_doctype` prop on it is a silent no-op (proven: `<Autocomplete>` shows an
   empty list). `LinkField` is the real implementation of this rule: it debounces the
   typed query and calls `frappe.desk.search.search_link`, which honors any `get_query`
   registered for that doctype (via `hooks.py standard_queries`, controller `set_query`,
   etc.) — the same code path the Desk Link field uses. Use `<LinkField :doctype="...">`
   for every link picker; never pass `reference_doctype` to a bare `<Autocomplete>`.

3. **Writes / multi-step actions → reuse `cashew_integration/api.py` whitelisted
   methods.** Every such method MUST call `frappe.has_permission(doctype, ptype,
   doc=...)` at entry. New write endpoints follow the same rule.

4. **Aggregates → one purpose-built custom endpoint per surface** (e.g.
   `dashboard_summary`). Internally use `frappe.get_all(... ignore_permissions=False)`
   so row-level perms still apply during aggregation.

**Why:** Any role permission change or Link `get_query` change reflects in the SPA
immediately, with zero code change. Mirrors how Frappe CRM and Helpdesk are built.

**Source decision:** `.fb/features/f010-cashew-frontend-spa/arch/decisions.md` →
Decision 5 (2026-05-24).

## SPA Design Philosophy (binding — read before any SPA styling)

Full doc: **`.fb/system-arch/design-philosophy.md`**. Codified 2026-06-02 after a
run of UI bugs that all traced to the same few causes. Pointed summary:

1. **Surfaces are opaque via frappe-ui design tokens** (`bg-surface-modal`, etc.).
   The preset is wired and emits the `:root` vars. A "see-through" menu/modal is
   **almost never** a missing background — **never** add `background:#fff`
   overrides to frappe-ui components. The cause is nearly always stacking (#2).
2. **Z-layer scale (the #1 recurring bug).** frappe-ui Dialog renders inline and
   Dropdown teleports to `body`, both with **no z-index** — app chrome paints over
   them and the page "bleeds through". Fixed scale, do not exceed:
   sticky table header `z-10` · in-page chrome `z-20`–`z-30` · app nav `z-40` ·
   **overlays (menus, dialogs, drawers, toasts) `z-50`**. Enforced globally in
   `src/index.css` (`.dropdown-content` / `.dialog-overlay { z-index: 50 }`).
   Never give in-page chrome `z ≥ 50`; never raise an overlay above 50.
3. **Rounding:** cards/tables/modals/popovers `rounded-lg`; inputs/selects/buttons/
   checkboxes `rounded`; pills/tags/chips/badges `rounded-full`. Square checkboxes
   are a bug — add `rounded border-gray-300 text-[var(--cs-accent)]`.
4. **Icons:** use Button `:icon-left` / `:icon-right` props (auto-aligned), never a
   hand-placed `<Icon class="mr-1">` in the default slot.
5. **Controls:** prefer frappe-ui (`<Button>`, `<Input>`, `<Autocomplete>`/`<Link>`)
   over native `<select>`/`<input>`; if native is unavoidable, match #3.
6. **Accent:** only `var(--cs-accent*)` / the `cs.accent` Tailwind color — never a
   hardcoded hex.
7. **Affordances:** primary row actions are visible at the row; the kebab holds
   only secondary/rare actions.

> If a fix seems to need `!important`, a forced background, or `z > 50` — stop and
> re-diagnose against the doc; it's almost certainly #2 (stacking) or #1.

## SPA hosting (introduced for f010)

- Pattern: Doppio-style `www/` route, identical to Frappe CRM and Helpdesk.
- Mount: `/cashew/<path:app_path>` catch-all → `cashew_integration/www/cashew.html`
  → Vue Router (HTML5 history) takes over client-side.
  Live state per `hooks.py` website_route_rules (verified 2026-05-25).
- Entry: `cashew_integration/www/cashew.py` does perm check + boot dict
  injection (csrf_token, session_user, sysdefaults, cashew_settings, …).
- **Role gate:** access granted to users holding Role `System Manager` OR
  `Accounts Manager`. No new role fixture introduced by f010.
- Auth: same-origin Frappe session cookie + CSRF from `window.boot.csrf_token`.
  No API keys in `localStorage`.
- Build: `bench build --app cashew_integration` triggers `yarn build` in
  `frontend/` via Doppio `build.json` hook. Commit `www/cashew.html` (tiny shell);
  gitignore `public/frontend/` and `frontend/node_modules`.
- **PWA installable (c014, 2026-05-25).** Two extra route rules ahead of
  the catch-all:
  - `/cashew/sw.js` → custom page_renderer (`cashew_integration.pwa.CashewPWAFile`)
    serves the built `public/frontend/sw.js` with header
    `Service-Worker-Allowed: /cashew/` so SW scope covers the SPA root
    (required for Chrome install criteria — SW must control `start_url`).
  - `/cashew/manifest.webmanifest` → same renderer, **dynamic**: builds the
    manifest JSON each request, resolving `theme_color` from
    `Cashew Settings.accent_color` (preset → hex via `ACCENT_PRESETS`
    mirror of `frontend/src/theme.js` PRESET_TABLE; Custom hex passthrough;
    Indigo fallback on invalid).
  - SW registration in `frontend/src/main.js`: PROD-only,
    `navigator.serviceWorker.register('/cashew/sw.js', { scope: '/cashew/' })`.
  - VitePWA configured with `manifest: false` (dynamic endpoint is the
    single source of truth) and `inlineWorkboxRuntime: true` (self-contained
    sw.js, no separate workbox-*.js to fetch).
  - `ThemeController.applyToRoot` also updates `<meta name="theme-color">`
    at runtime so browser chrome retints when accent changes; the installed
    PWA's manifest theme_color is locked at install time.
- **Icon family (c015, 2026-05-25).** All **five** icon surfaces use
  MIT-licensed open-source glyphs — no in-house icon design.
  - **Legacy `/desk` apps grid (the v16 default landing for many users):**
    rendered from `Desktop Icon` DocType — NOT from `add_to_apps_screen`.
    Fixture at `cashew_integration/desktop_icon/cashew_integration.json`
    (icon_type="App", logo_url points to the SVG below). Without this row
    the cashew tile does NOT appear at `/desk` even if every other hook
    is correct. ERPNext + Frappe ship the same kind of JSON fixture per app.
  - Desk apps-screen tile (`add_to_apps_screen[0].logo`) + `app_logo_url`:
    `cashew_integration/public/images/cashew-integration-logo.svg`.
  - Cashew SPA / PWA: `frontend/public/favicon.svg`. PWA install PNGs
    (64/192/512 + maskable-512 + apple-touch-180 + favicon.ico) generated
    by `@vite-pwa/assets-generator` (`minimal-2023` preset) from this SVG.
  - Cashew-internal logo affordance (`app_icon_url`):
    `cashew_integration/public/images/cashew-app-icon.svg`.
  - All three SVGs ship the same glyph: **Tabler Icons `chart-donut`
    (filled)**, MIT, `fill="#4f46e5"` (matches default
    `Cashew Settings.accent_color` = Indigo so first paint is coherent).
  - Workspace sidebar icon: lucide `chart-pie` (set in the workspace
    JSON `icon` field; lucide is Frappe's bundled v16 sprite — no
    fixture or `app_include_icons` entry needed).
  - When changing the icon: replace those three SVGs from a library
    (lucide/tabler/phosphor/heroicons all OK; keep MIT/ISC), then run
    `cd frontend && npx @vite-pwa/assets-generator --preset minimal-2023
    public/favicon.svg` to regen the PNGs, then `bench build --app
    cashew_integration`. The `Desktop Icon` fixture and workspace JSON
    keep working unchanged (they reference the asset path).
- **Responsive v1.** All SPA surfaces (runs list, run detail, dashboard) usable
  on mobile and tablet, not desktop-only. Use frappe-ui responsive primitives.
- "Back to Desk" link in the SPA shell points to `/app` (ERPNext home).

**Source decisions:** `.fb/features/f010-cashew-frontend-spa/arch/decisions.md` →
Decisions 1–4 (2026-05-24); `feature.yaml` component c014 (2026-05-25).

## Other surfaces in this app (not the SPA)

- **Desk forms** for `Cashew Settings`, `Cashew Category Mapping`, `Cashew Account
  Mapping`. Configuration UX stays on Desk for now (f010 explicit OOS).
- **Frappe Page `cashew-row-explorer`** (Vue 3 single-bundle, not a SPA) at
  `/app/cashew-row-explorer/<run-name>`. Built for f006 row-level investigation +
  fix flow. Independent Desk-side surface. f010 does NOT link to it, embed it, or
  replace it — the SPA Run Detail owns its own row-level UX natively
  (see `.fb/features/f010-cashew-frontend-spa/arch/decisions.md` Decision 7).
- **CSV-driven import flow** (f001) runs through the `Cashew Import Run` Desk form.
  SPA provides a more operator-friendly surface for the same DocType from f010
  onward; the Desk form is still available.
