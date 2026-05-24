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
- Mount: `/frontend/<path:app_path>` catch-all → `cashew_integration/www/frontend.html`
  → Vue Router (HTML5 history) takes over client-side.
  **Note (2026-05-24):** arch decision D2 originally specified `/cashew/*`;
  Dev shipped the bench `add-spa` default `/frontend/*` at user request.
  Apps-screen tile + Vue Router base both point at `/frontend`.
- Entry: `cashew_integration/www/frontend.py` does perm check + boot dict
  injection (csrf_token, session_user, sysdefaults, …).
- **Role gate:** access granted to users holding Role `System Manager` OR
  `Accounts Manager`. No new role fixture introduced by f010.
- Auth: same-origin Frappe session cookie + CSRF from `window.boot.csrf_token`.
  No API keys in `localStorage`.
- Build: `bench build --app cashew_integration` triggers `yarn build` in
  `frontend/` via Doppio `build.json` hook. Commit `www/cashew.html` (tiny shell);
  gitignore `public/frontend/` and `frontend/node_modules`.
- **PWA on.** `vite-plugin-pwa` is kept; manifest + service worker shipped.
  Service worker is intentionally future-proofing for an installable surface,
  not used for offline work in v1.
- **Apps-screen tile:** label `"Cashew"`, custom SVG icon committed at
  `cashew_integration/public/images/cashew-app-icon.svg`.
- **Responsive v1.** All SPA surfaces (runs list, run detail, dashboard) usable
  on mobile and tablet, not desktop-only. Use frappe-ui responsive primitives.
- "Back to Desk" link in the SPA shell points to `/app` (ERPNext home).

**Source decisions:** `.fb/features/f010-cashew-frontend-spa/arch/decisions.md` →
Decisions 1–4 (2026-05-24).

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
