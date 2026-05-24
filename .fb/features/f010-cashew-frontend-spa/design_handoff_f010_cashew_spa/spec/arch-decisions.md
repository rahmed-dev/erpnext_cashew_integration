# f010 — Cashew Frontend SPA (Runs + Dashboard) — Architecture Decisions

Feature: f010 Cashew Frontend SPA
Owner: bmad-fb-architect
Status: in-progress (decisions recorded as user confirms)
Started: 2026-05-24

Scope (from feature.yaml; updated 2026-05-24 by UI phase — see D9/D10/D11):
- **Finance dashboard** as SPA landing — P&L (income/expense charts) + balance-sheet
  snapshots (cash/bank, receivable) over a selectable period. Replaces the original
  run-aggregate dashboard concept (D9).
- **Imports list** — list of all Cashew Import Runs, entry point to open existing or
  create new.
- **Run workspace** — unified create + work + view surface for a single Cashew
  Import Run. State-driven sections (Upload / Preview / RowsWorkbench /
  CompletedSummary) cover the full lifecycle (Draft → Parsed → Validated → Queued →
  Completed/Reverted). Replaces the original "Run Detail" page (D10).
- Doppio-pattern SPA inside `cashew_integration` app
- OOS: settings/mapping config UI (stays on Desk), public-portal, Row Explorer
  replacement, role-gated per-page route hiding

Dependencies: f009 done (period_start / period_end on Cashew Import Run).
Blockers: none.

---

## Decision 1 — Scaffold via Doppio CLI; keep frappe-ui (2026-05-24)

**Decision:** Use Doppio's `bench get-app doppio` + `bench add-pwa-to-app cashew_integration` to bootstrap the SPA. Output folder under `apps/cashew_integration/dashboard/` (Doppio default name). Keep `frappe-ui` (Tailwind + Frappe components) in `package.json` for v1.

**Rationale:**
- Doppio CLI is the established community pattern for embedding Vite + Vue 3 inside a Frappe app; matches Gameplan / HRMS dashboard / Builder shape — future maintainers recognize it.
- Auth piggyback (`frappe.session.user`, `window.csrf_token`) + dev HMR proxy come configured out of the box. Hand-rolling these reimplements ~half a day of boilerplate Doppio already solves.
- `frappe-ui` is the default — kept because the cost of stripping it is small and it accelerates v1 component layout. Revisit if a different design system is adopted later.

**Trade-off accepted:** Doppio convention lock-in — folder name, manifest path, included libs. Updates to Doppio template will require manual sync. Acceptable given the team velocity win.

**Sub-decisions:**
- D1.a (2026-05-24, closed) — **Keep PWA support.** `vite-plugin-pwa` stays in `vite.config.js`; manifest.json + service worker are produced by the build. Rationale: cheap to keep, leaves the door open to a future installable / offline-capable surface without a re-scaffold.
- D1.b (open) — Doppio version pin: TD/Dev to record the doppio commit / release used at scaffold time so a re-scaffold reproduces the same baseline.

---

## Decision 2 — Host shape: `www/` web page + HTML5 history, same as Frappe CRM (2026-05-24)

**Decision:** Mount the SPA as a Frappe `www/` web page with a catch-all `website_route_rules` entry. Identical pattern to Frappe CRM (verified in `bench-15/apps/crm/`) and Frappe Helpdesk.

Concrete shape inside `apps/cashew_integration/`:

```
frontend/                              ← Vite project (Vue 3 + frappe-ui + Pinia + vue-router)
  package.json                           build script: vite build --base=/assets/cashew_integration/frontend/
                                                       && cp ../cashew_integration/public/frontend/index.html
                                                              ../cashew_integration/www/cashew.html
  vite.config.js                         frappeProxy:true, lucideIcons:true, jinjaBootData:true,
                                         buildConfig.indexHtmlPath = ../cashew_integration/www/cashew.html
  src/router.js                          createWebHistory()   ← HTML5 history, no hash
cashew_integration/
  hooks.py                              website_route_rules = [
                                          {"from_route": "/cashew/<path:app_path>", "to_route": "cashew"},
                                        ]
                                        + app_icon_url, app_icon_route="/cashew" (Apps screen tile)
  www/
    cashew.html                         ← built SPA shell (committed; rebuilt on `bench build`)
    cashew.py                           ← no_cache=1; get_context() runs perm check, raises
                                           PermissionError on deny → Frappe redirects to login;
                                           injects boot dict {csrf_token, session_user, sysdefaults,
                                           default_company, default_currency, ...}
  public/frontend/                      ← built JS/CSS assets (gitignored; produced by build)
```

Routes mounted client-side under `/cashew` (updated 2026-05-24 — see D9/D10):
- `/cashew` → finance dashboard (landing)
- `/cashew/runs` → imports list
- `/cashew/runs/new` → run workspace, fresh state (CSV upload entry)
- `/cashew/runs/:run_name` → run workspace, state-driven on the run's current stage

Row Explorer stays where it is (`/app/cashew-row-explorer/<run-name>`); SPA does NOT link to or embed it (D7).

**Rationale:**
- This is the *primary operator surface* for cashew imports — full-screen real estate matters more than Desk chrome.
- Identical to CRM/Helpdesk pattern; matches Doppio's default `add-pwa-to-app` output. Zero swimming against the framework.
- HTML5 history → clean, bookmarkable, shareable URLs ("send me /cashew/runs/IMP-0001").
- Auth + boot data handled by `cashew.py` once; JS just reads `window.boot`. No login plumbing leaks into the bundle.
- Apps-screen tile (`app_icon_route="/cashew"`) gives operators a one-click entry from the ERPNext landing page.

**Trade-off accepted:**
- Outside Desk chrome — no sidebar/breadcrumb. Operators must use the SPA's own nav. Acceptable: the SPA *is* the nav for cashew flows; Desk navigation back is handled by an explicit "Back to Desk" link in the SPA shell.
- Catch-all rule consumes the `/cashew` namespace. Cheap — cashew_integration owns that namespace anyway.

**Sub-decisions (all 2026-05-24, closed):**
- D2.a — **Apps-screen tile = label `"Cashew"` + custom SVG icon (built as part of f010).** Icon asset to be authored during dev pass, committed at `cashew_integration/public/images/cashew-app-icon.svg`, wired via `app_icon_url` in `hooks.py`. No placeholder.
- D2.b — **"Back to Desk" link target = `/app` (ERPNext / Desk home).** Single, predictable exit point. UI may also surface the Apps-screen tile as a return path, but the in-shell link is `/app`.
- D2.c — **Mobile-responsive v1.** Runs list, run detail, and dashboard are all built responsive so accountants can use the SPA on mobile / tablet. Leverages frappe-ui's responsive primitives. UI wireframes must include mobile breakpoints alongside desktop.

---

## Decision 3 — Auth via Frappe session cookie + CSRF from boot (2026-05-24)

**Decision:** Same-origin Frappe session cookie + CSRF token injected via Jinja boot data. No API key/secret in JS storage. Identical to CRM/Helpdesk.

Mechanics:
- `cashew.py` `get_context()` returns a `boot` dict including `csrf_token = frappe.sessions.get_csrf_token()`, `session_user = frappe.session.user`, plus any cashew-specific defaults (`default_company`, `default_currency`, etc.).
- Vite plugin `jinjaBootData: true` exposes that dict on `window.boot` after page load.
- `/api/*` calls go to same origin → browser sends session cookie automatically. SPA adds `X-Frappe-CSRF-Token: window.boot.csrf_token` header. `frappe-ui` `createResource` / `useCall` do this out of the box.
- Unauthenticated access: `check_app_permission()` in `cashew.py` raises `PermissionError` → Frappe redirects to `/login?redirect-to=/cashew`.
- Session expiry mid-session: 403 from `/api/*` → SPA detects, redirects to `/login?redirect-to=/cashew/<current-path>`.

**Rationale:**
- f010 is same-origin, behind Frappe login, internal users only. Token model's only real benefit (off-domain hosting) does not apply.
- Avoids storing secrets in `localStorage` (XSS exposure surface).
- `frappe-ui` resources expect this model — picking anything else means working against library defaults.
- Matches CRM/Helpdesk, which D1/D2 already chose to mirror.

**Trade-off accepted:** Bundle is non-portable to off-domain hosts. Not a constraint for f010 — operators always use the same ERPNext site.

**Sub-decisions:**
- D3.a (2026-05-24, closed) — **Role gate = `System Manager` OR `Accounts Manager`.** No new role fixture introduced by f010. `cashew.py` `check_app_permission()` returns True if the session user holds either role. Rationale: both roles already exist; accountants who already run cashew imports via Desk have `Accounts Manager`, so the SPA is reachable for them on day one with no admin work.
- D3.b (open) — 403 → re-login flow: preserve current SPA route on bounce. Exact handling (query param shape, post-login redirect) is TD-time.

---

## Decision 4 — Build pipeline via `bench build` hook; commit `cashew.html`, gitignore `public/frontend/` (2026-05-24)

**Decision:** Wire the SPA build into `bench build --app cashew_integration` using Doppio's `build.json` trigger pattern (what CRM uses). No separate CI step. Bundle is rebuilt on every `bench build` and on `bench update`.

Repo discipline:
- **Commit** `cashew_integration/www/cashew.html` (tiny, just `<script src>`/`<link>` references to built assets; Frappe needs it on disk to serve the route).
- **Gitignore** `cashew_integration/public/frontend/` (heavy, regenerated on every build).
- **Commit** `frontend/package.json`, `frontend/yarn.lock`, `frontend/vite.config.js`, all of `frontend/src/`, etc.
- **Gitignore** `frontend/node_modules/`, `frontend/dist/`.

Build commands:
- Production: `bench build --app cashew_integration` → triggers `yarn install && yarn build` inside `frontend/` via `build.json` → outputs to `cashew_integration/public/frontend/` + copies `index.html` to `cashew_integration/www/cashew.html`.
- Dev loop:
  - Terminal 1: `bench start` (Frappe on `:8000`).
  - Terminal 2: `cd apps/cashew_integration/frontend && yarn dev` (Vite on `:8080` with HMR; `frappeProxy: true` proxies `/api/*` to `:8000`).
  - Browser: `http://<site>:8080/cashew` for development; `http://<site>:8000/cashew` once `yarn build` has been run for testing the production path.

**Rationale:**
- Mirrors CRM/Helpdesk; one of the most well-trodden Frappe build patterns. Zero novelty risk.
- Production deploys keep working via vanilla `bench update` / `bench build` — no extra CI plumbing, no Frappe Cloud incompatibility.
- Committed `cashew.html` keeps Frappe's website route serving correctly even before the first local `bench build` after a fresh clone (deferred build is fine; serving without the html is not).
- Gitignoring `public/frontend/` keeps git history clean — these are pure derived artifacts.

**Trade-off accepted:** Production servers need Node + Yarn installed. Standard on any Frappe v15/v16 bench (`bench` already needs them for vanilla asset bundling), so this is not a new constraint.

**Open within this decision:**
- D4.a: Production Node/Yarn version pinning — TD to fix in `package.json` `"engines"` to whatever the existing bench uses (Node 18+ standard for Vite 4).
- D4.b: `bench build` integration mechanics — Doppio scaffold writes the necessary `build.json` and shim; TD confirms it runs cleanly inside this bench. If Doppio's hook doesn't trigger reliably on this bench's Frappe version, fallback is a `before_install` / `after_install` Python hook that shells out to `yarn build`.
- D4.c: CI gate — out of f010 scope, but worth flagging: any future CI should run `yarn build` to catch broken bundles before merge.

---

## Decision 5 — Hybrid API: `frappe.client.*` for reads, custom whitelisted for writes/aggregates, frappe-ui Autocomplete for Link selectors (2026-05-24)

**Decision:** Use a disciplined hybrid that lets Frappe enforce role permissions and Link field query filters automatically, while keeping mutations behind explicit whitelisted methods that already exist in `cashew_integration/api.py`.

**The four rules (binding for f010 SPA and any future SPA work in this app):**

1. **Reads always go through `frappe.client.get_list` / `frappe.client.get_doc` / `frappe.client.get_count`.**
   Never wrap them in a custom endpoint. Frappe's standard handler applies DocPerm + User Permissions + If-Owner + field-level perms automatically. Re-implementing in a custom endpoint = drift risk.

2. **Link field selectors always use `frappe-ui` `<Autocomplete>` (or the underlying `/api/method/frappe.desk.search.search_link` call) with `reference_doctype` + `reference_fieldname` set.**
   This routes through Frappe's standard `search_link` handler, which honors any `get_query` registered for that field (via `hooks.py standard_queries`, doctype controller `set_query`, or `frappe.utils.set_default`). Existing Link filters on `Cashew Import Run` / `Cashew Import Row` / `Cashew Category Mapping` keep working in the SPA verbatim — same code path as the desk form.

3. **Writes / multi-step actions reuse the existing whitelisted methods in `cashew_integration/api.py`.**
   These already exist from f001 / f004 / f006 (`parse_and_preview`, `validate_import`, `queue_run`, `revert_run`, `set_row_party`, `resolve_validation`, etc.). Every such method must call `frappe.has_permission(doctype, ptype, doc=...)` at entry — explicit, one line, matches the existing pattern. New write endpoints follow the same rule.

4. **Dashboard aggregates get one new custom endpoint** (working name: `cashew_integration.api.dashboard_summary`).
   Internally uses `frappe.get_all(... ignore_permissions=False)` — row-level perms still apply during aggregation. Returns `{runs_by_status, totals_by_period, recent_activity, ...}`. Strawman shape; TD finalizes during component spec.

**Rationale:**
- Best balance between not reinventing Frappe (rules 1, 2) and keeping domain logic discoverable (rules 3, 4).
- Identical posture to CRM/Helpdesk (which D1/D2/D3 already mirror): `frappe.client.*` for CRUD, custom whitelisted for the rest.
- Critical user-stated constraint preserved: any role permission change or Link `get_query` change reflects in the SPA with **zero code change**.

**Trade-off accepted:** Two API styles in one codebase. Acceptable because the split is principled (read = CRUD, write/aggregate = domain), and it matches what other Frappe SPAs do.

**Open within this decision:**
- D5.a: `dashboard_summary` exact response shape — TD to finalize.
- D5.b: Audit existing `api.py` endpoints (f001/f004/f006) for `frappe.has_permission` calls; add where missing as part of f010 dev. Not a refactor of those features — just a pre-flight check.
- D5.c: SPA must surface "Permission denied" / "Not allowed" responses cleanly (toast + don't crash the route). UI spec point.

**Reflected in app CLAUDE.md:** Yes — see `apps/cashew_integration/CLAUDE.md` "SPA API discipline" section, written 2026-05-24 alongside this decision.

---

## Decision 6 — State management approach: deferred to TD (2026-05-24)

**Decision:** No state-management library or pattern bound at architecture time. Pinia, composables-only, and `frappe-ui` resources alone are all viable; the choice is an implementation detail that TD can make once the page inventory and component breakdown are in hand.

**Why deferred:** State management is a Vue-ecosystem implementation detail, not an architecture-level constraint. The rules that *are* architecture (API discipline in D5, host shape in D2, auth in D3) hold regardless of which state layer TD picks. Binding it now risks over-specifying.

**Constraints that bind any future choice:**
- Whatever pattern TD picks must respect D5 — reads via `frappe.client.*`, Link selectors via `<Autocomplete>` with `reference_doctype` + `reference_fieldname`, writes via existing `api.py` whitelisted methods, aggregates via `dashboard_summary`.
- No `localStorage`/sessionStorage persistence of view state (per user direction during D6 conversation — view prefs reset on every fresh page load). If TD reaches for Pinia, it does so *without* `pinia-plugin-persistedstate`.

---

## Decision 7 — SPA Run Detail owns row-level UX natively; Row Explorer untouched by f010 (2026-05-24)

**Decision:** The SPA Run Detail page (c006) is designed to fully cover the row-level operator workflows on its own — table view, filters, column presets, inline party edit, validation-fix modal, bulk actions, status pills, search. The existing `cashew-row-explorer` Frappe Page (f006 c006) is **not part of the SPA**, not linked from the SPA, not embedded, not replaced by f010. It remains as an independent Desk-side surface untouched by this feature.

**Why:** Bolting the SPA onto a Desk Page introduces two competing UIs over the same data with no shared state, two style systems, and round-trip navigation friction. Native row-level UX inside the SPA keeps one coherent surface for operators, matches the rest of the SPA's frappe-ui look, and removes any need for an integration contract between the two.

**What this means for downstream agents:**
- **UI (bmad-fb-ui):** Run Detail wireframes must include the row-level UX surface end-to-end (table, filters, presets, inline edit, fix modal, bulk select + bulk party-set, search). Treat it as a first-class component of Run Detail, not an optional drill-out. Use frappe-ui's table / form / modal primitives.
- **TD (bmad-fb-td):** c006 spec covers row-level interactions natively. No SPA-side wrapper or proxy for `cashew-row-explorer` — that DocType / Frappe Page / bundle stays outside f010's blast radius.
- **No cascade to f006.** Row Explorer code (c006/c007 of f006) is unaffected by f010 architecture. Whether it's deleted, deprecated, or kept long-term is a separate future decision; not in scope for f010.

**Trade-off accepted:**
- c006 (SPA Run Detail) scope is meaningfully larger than a typical detail page — it has to do real row-level operations. UI/TD must size accordingly.
- Two surfaces for row work coexist post-f010 (SPA Run Detail + Desk Row Explorer). Acceptable because operators will naturally migrate to the SPA; the Desk surface is a fallback, not a competing workflow.

**Open within this decision:** None. Closed.

---

## Decision 8 — Frappe realtime via Socket.IO; SPA listens for `Cashew Import Run` doc updates (2026-05-24)

**Decision:** SPA opens a Socket.IO connection to Frappe (`/socket.io`) on mount and listens for realtime `doc_update` events scoped to `Cashew Import Run`. No periodic polling. Identical posture to CRM/Helpdesk.

Mechanics:
- `socket.io-client` ships in the SPA bundle (already a peer of `frappe-ui`, near-zero new weight).
- On mount, SPA subscribes via `frappe.realtime` helpers to:
  - `Cashew Import Run` list-level updates (any run changes status → runs list + dashboard refresh).
  - `Cashew Import Run` doc-level updates for the currently-viewed run (instant status / counter updates on Run Detail).
- Server side: `cashew_integration` background workers must trigger Frappe's standard `doc_update` event when they mutate run state. `frappe.db.set_value()` and `doc.save()` do this automatically; raw SQL updates do not — TD/Dev to audit existing worker code and add `frappe.publish_realtime(...)` where needed.
- Reconnect: socket-client auto-reconnects on transient drops. SPA shows a "Reconnecting…" indicator only after sustained failure (>10s); during the gap, last known state is shown (no stale-data crash).

**Rationale:**
- Frappe emits `doc_update` events for free on `save()` / `set_value()`. Cashew's existing flow already uses these. Confirming end-to-end is a quick verification, not new infrastructure.
- Polling for a runs list that may be quiet for hours wastes requests; polling fast enough to feel responsive on an in-flight run wastes more. Socket.IO is the established Frappe pattern for exactly this case.
- `socket.io-client` is already pulled in via `frappe-ui`; no new dependency footprint.
- Production: `redis-cache` and `socketio` services are part of standard `bench start`. No infra change.

**Trade-off accepted:** Requires Socket.IO service running. Already standard on every Frappe v15/v16 bench — not a new constraint. SPA bundle gains a small connection-status indicator. Acceptable.

**Open within this decision:**
- D8.a: Exact event names + emission points — TD to spec. Strawman: subscribe to `doc_update` filtered to `doctype=Cashew Import Run`; emit on every state transition inside the cashew worker (`Queued` → `Validating` → `Posting` → `Posted` / `Failed`).
- D8.b: Backend audit — Dev to confirm every state mutation in `cashew_integration` either goes through `frappe.db.set_value()` / `doc.save()` (auto-emits) or explicitly calls `frappe.publish_realtime()`. Bare SQL updates would silently break realtime.
- D8.c: Fallback when socket connection fails permanently — degrade to 30s polling rather than going dark. TD-time spec.

---

## Decision 9 — Dashboard is finance overview, not run aggregates (2026-05-24, UI phase)

**Decision:** The SPA's dashboard surface is a **finance dashboard** (P&L pie + balance-sheet snapshots), NOT the run-aggregate dashboard described in the original feature.yaml scope. The dashboard is the SPA landing route (`/cashew`).

**Concrete content (strawman; TD finalizes shape):**
- Income vs Expense pie (or stacked chart) for a selectable period.
- Top categories by income, top categories by expense.
- Balance-sheet snapshot tiles: Total Cash/Bank, Total Receivable, Total Payable (and any other CFO-level totals user finds useful at TD time).
- Recent activity / drill-in to recent imports — kept lightweight; the imports-list page is the real drill-in surface.
- Period selector (defaults to current month / last 30 days; TD to confirm).

**Data source:** GL Entry + Account balances, NOT Cashew Import Run aggregates. This is a real change in `dashboard_summary` shape vs D5's original strawman.

**Why:** User direction (UI phase, 2026-05-24). The original run-aggregate dashboard answered an operator question ("how are imports going"); the finance dashboard answers a manager/CFO question ("how is the business doing"). Manager view is the higher-leverage landing experience for a finance-import app. Operator drill-in moves to imports-list page.

**What this means for downstream agents:**
- **TD:** Re-spec `dashboard_summary` endpoint to return GL-derived aggregates: income/expense by period (grouped by `Account.account_type` or category mapping), cash/bank totals from Account balances, receivable/payable balances. Internally: `frappe.db.sql` or `frappe.get_all` over `GL Entry` + `Account`, scoped by company + period. Rule 4 of D5 still binds (one endpoint, `ignore_permissions=False`).
- **TD:** Pick a charting library at component-spec time. Strawman: `frappe-ui`'s built-in chart wrapper or `chart.js` if frappe-ui's coverage is insufficient. Lightweight — no dashboarding framework (no Apache ECharts unless TD has a strong reason).
- **Dev:** `cashew_integration/api.py` gains `dashboard_summary` (or similar) with `frappe.has_permission("GL Entry", "read")` gate at entry.

**Out of scope for D9:**
- Account/company switcher widget — TD's call on whether v1 needs it or just reads default company from boot.
- Persisted user preferences for dashboard period — D6's no-localStorage constraint still binds; period selection is session-only.
- Drill from chart slices into transaction lists — future feature, not v1.

**Open within this decision:**
- D9.a: Exact tile/chart inventory — TD to lock during c007 component spec, in conversation with user.
- D9.b: Default period — current month, last 30 days, or fiscal year-to-date? TD to pick a sensible default that doesn't require a click-to-see-anything UX.

---

## Decision 10 — Run workspace unifies create + work + view; component list restructured (2026-05-24, UI phase)

**Decision:** Drop the old "Runs list / Run detail / Dashboard" split. The SPA has three pages, restructured as follows:

| Old component (arch v1) | New component (UI phase) | Description |
|---|---|---|
| c005 `runs-list-page` | c005 `imports-list-page` | List of all Cashew Import Runs, filters, "+ New Import" button. Functionally same as before; renamed for clarity. |
| c006 `run-detail-page` | c006 `run-workspace-page` | **Unified create + work + view surface.** Single component, single route family (`/runs/new` and `/runs/:run_name`), state-driven sections that render based on the run's current stage. |
| c007 `dashboard-page` | c007 `finance-dashboard-page` | Finance dashboard (see D9). Renamed + scope shift. |

The state-driven sections inside c006 are first-class extension points:
- `UploadSection` — Draft state. CSV file picker, parse trigger.
- `PreviewSection` — Parsed state. Row preview + parse stats. Validate trigger.
- `RowsWorkbench` — Validating / Validated states. Full row-level UX (D11). Validate / Queue triggers.
- `CompletedSummary` — Queued / Posted / Reverted states. Read-mostly results view + revert action.

**Why:** User mental model (UI phase, 2026-05-24) treats "new import" and "view existing run" as one operator workspace, not two separate pages. The lifecycle is incremental — Draft → Parsed → Validated → Queued — and the operator works the same surface through it. Splitting create vs view forces a context switch the data shape doesn't require.

**What this means for downstream agents:**
- **TD:** c006 spec includes the section-slot architecture explicitly. Each section is its own Vue subcomponent under `src/pages/RunWorkspace/sections/`. The parent (`RunWorkspacePage.vue`) is the section router — picks which section to render based on `run.status`.
- **TD:** `/runs/new` route loads c006 with a synthesized empty run object (no DB record yet); UploadSection's "Parse" action creates the actual `Cashew Import Run` record via existing `api.parse_and_preview` and then router-replaces to `/runs/:run_name`.
- **Dev:** No new endpoints required by this restructure — same backend as today's Desk form (`parse_and_preview`, `validate_import`, `queue_run`, `revert_run`, etc.). Frontend orchestration only.

**Trade-off accepted:**
- c006 is larger than a typical Vue page component (parent + four sections + the row workbench). Acceptable: the section-slot pattern keeps each piece small and independently testable.
- Two URL shapes (`/runs/new` vs `/runs/:run_name`) resolving to one component requires careful route-guard handling (parse-success must `router.replace`, not `router.push`, to avoid back-button landing on `/runs/new` with a stale empty state). TD to spec.

**Open within this decision:**
- D10.a: Should completed runs be read-only or allow re-queuing failed rows? TD-time UX call in conversation with user.
- D10.b: Where does the "Revert" action live within `CompletedSummary` — primary button, danger zone footer, or kebab menu? UI wireframe call.

---

## Decision 11 — Run workspace ships full row-level UX today, extensible for future row features (2026-05-24, UI phase)

**Decision:** `RowsWorkbench` (the row-level section inside c006) ships **the full row-level UX surface in f010 v1** — table view, filters (status, txn_type, category_type, category, raw_account, posted state), column presets, inline party edit, validation-fix modal, bulk select + bulk party-set, search, status pills. Architecture inside the workbench is intentionally extensible so future row-level features can be added without restructuring.

**Concrete extensibility shape (TD to refine):**
- `RowsWorkbench.vue` is a layout shell — toolbar, filter bar, table, modal portal.
- Row actions are registered, not hardcoded — array of action descriptors (`{ id, label, icon, applies(row), exec(rows) }`). Adding a future bulk action means adding a descriptor, not touching the toolbar layout.
- Column definitions are declarative — array of column descriptors (`{ key, label, type, sortable, filterable, formatter, editable }`). New columns mean adding a descriptor.
- Modal portal exposes named modals; new fix flows register a new modal name + component, no surgery on the parent.

**Why "build full today, extensible structure":** User direction (UI phase, 2026-05-24) — "build as much as possible". The row-level surface is the bulk of an operator's working time; shipping a thin version first means operators won't migrate from the Desk form / Row Explorer. Full coverage today + extensible scaffolding means future row-features (e.g., bulk category override, undo last party-set, row-level diff vs prior import) can be added cheaply without rewriting the workbench shell.

**Closes:** D7 (it asked UI to decide row-level UX placement — answer: inside `run-workspace-page` → `RowsWorkbench` section, full coverage, declarative extension points).

**Trade-off accepted:**
- More upfront work in c006 spec + dev. Acceptable per user "build as much as possible".
- Declarative action/column registries cost a small amount of indirection vs hardcoded UI. Worth it given operator-flow plasticity.

**Open within this decision:**
- D11.a: Action registry shape — TD-time API design call (in-component composable vs Pinia store vs static module).
- D11.b: Column-preset persistence — D6 binds: session-only (no localStorage), preset state lost on page reload. UI to confirm operator-flow impact is acceptable.

---

## UI-phase scope flag (open) — UI-driven DocType field additions

**Flag (open, 2026-05-24, UI phase):** During wireframe + component-breakdown work, UI may identify that the import workspace would be materially clearer if `Cashew Import Run` (parent) or `Cashew Import Row` (child table) gained one or more new fields. User explicitly authorized this kind of request during UI phase ("we are open to adding new fields in the doctypes and child table as needed").

**Rules:**
- UI captures any such request in the relevant page file (`{app}/.fb/ui/pages/{page}.md`) under a "DocType field requests" heading, including: field name, fieldtype, why UX needs it, which component depends on it.
- The flag itself is NOT a green light to implement. Architect/Dev must approve each addition before Dev does the doctype change.
- Approved additions get captured as their own decision (D12, D13, …) in this file, with a one-line summary in the parent feature.yaml `status_history`.

**Why:** Doctype schema changes are real architectural commitments (migrations, fixtures, downstream report assumptions). The UI phase is allowed to surface them but not to commit to them unilaterally.

**Status:** No concrete requests captured yet. Will accumulate as UI breakdown progresses.

---

## UI-phase scope flag (closed) — Per-page permission UX deferred

**Flag (2026-05-24, UI phase):** Per-page role-based route hiding is out of scope for f010 v1. The SPA does not gate navigation items or routes by role — every authenticated user (per D3.a's role gate at the app level) sees every page.

**D5.c still binds:** Any API call may return 403; the SPA must surface a graceful error (toast + don't crash the route). This is implemented once at the shell level (c004's global error boundary), not per-page.

**Why:** User direction (UI phase, 2026-05-24). Per-page route gating adds UX complexity (role-aware sidebar, redirect-from-forbidden-route, etc.) that the current user base (System Manager OR Accounts Manager only) doesn't need. Revisit if a "view-only" or "read-only auditor" role is ever introduced.

