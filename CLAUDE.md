# cashew_integration — Claude conventions

Per-app instructions for any future Claude session in this app.

## Source of truth: `.fb/`

This app is managed under the BMad Frappe Builder pipeline. Authoritative state:
- `.fb/system-arch/` — system-wide architecture decisions
- `.fb/features/{fid}-{name}/` — per-feature decisions, specs, reviews
- `.fb/features/index.yaml` — feature registry
- `.fb/pipeline.yaml` — current pipeline stage / handoff

Always check `.fb/` before making architectural assumptions.

## SPA API discipline (introduced for f010, applies to all future SPA work)

The Vue SPA (`/cashew`, see `f010-cashew-frontend-spa`) follows a hybrid API model that
preserves Frappe's role permission system and Link field query filters with zero
re-implementation. This is binding. Deviate only with an Architect decision record.

**Four rules:**

1. **Reads → `frappe.client.*`.** Use `frappe.client.get_list`, `frappe.client.get_doc`,
   `frappe.client.get_count` from the SPA. Never wrap a read in a custom whitelisted
   endpoint. Frappe applies DocPerm + User Permissions + If-Owner + field-level perms
   automatically through these handlers — re-implementing them in a custom endpoint
   risks drift.

2. **Link selectors → `frappe-ui` `<Autocomplete>` with `reference_doctype` +
   `reference_fieldname`.** This routes through `frappe.desk.search.search_link`, which
   honors any `get_query` registered for that field (via `hooks.py standard_queries`,
   doctype controller `set_query`, or `frappe.utils.set_default`). Same code path the
   Desk form uses. Existing query filters keep working in the SPA verbatim.

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
