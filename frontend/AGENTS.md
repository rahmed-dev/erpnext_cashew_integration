# Frontend SPA

## Purpose

Vue 3 SPA served at `/cashew/`. Frappe session-authenticated, PWA-installable. Provides the Cashew import dashboard, import run workspace, and finance overview.

## Ownership

- `src/App.vue` — root, router-view + Shell wrapper
- `src/boot.js` — frappe-ui bootstrap, reads `window.boot` injected by `www/cashew.py`
- `src/colorUtils.js` — accent color utilities; `PRESET_TABLE` must stay in sync with `cashew_integration/pwa.py` `ACCENT_PRESETS`
- `src/components/Shell/` — Sidebar, MobileTopBar, MobileBottomNav, AppSwitcher, NavItems, UserChip, RealtimeStatusIndicator
- `src/components/finance-dashboard/` — BalanceTile, BalanceTileGrid, BalanceDetailModal, AssetBreakdownCard, CategoryBreakdownCard, CategoryBreakdownList, CompanySelector, DashboardEmptyState, ImportCard, IncomeExpenseChart, PeriodSelector, RecentImportsStrip
- `src/components/imports-list/` — RunCard, RunRow, RunsCardList, RunsTable, FilterBar, CompanyFilter, StatusFilter, PeriodFilter, Pagination, RowKebabMenu, EmptyAllRuns, EmptyFilterMiss
- `src/components/run-workspace/` — RunHeader, StateStepper; sections: RowsWorkbench, UploadSection; upload: CompanyPicker, CsvDropzone, OptionalConfigDisclosure; workbench: ActiveFilterChips, BulkPartyModal
- `src/components/shared/LinkField.vue` — canonical Link picker; wraps `frappe.desk.search.search_link`; use for every link picker (never bare `<Autocomplete>`)
- `public/favicon.svg` — source icon for PWA PNG generation (Tabler `chart-donut` filled, `fill="#4f46e5"`)

## Local Contracts

- **API discipline** (binding): reads → `frappe.client.*`; link pickers → `<LinkField :doctype="...">`; writes → `api.py` whitelisted methods; aggregates → one purpose-built endpoint. Full rules in root `CLAUDE.md`.
- **PWA**: `vite-plugin-pwa` configured with `manifest: false` (dynamic endpoint owns the manifest) and `inlineWorkboxRuntime: true` (self-contained `sw.js`). SW registered PROD-only in `main.js` at scope `/cashew/`.
- **Theme**: `ThemeController.applyToRoot` updates `<meta name="theme-color">` at runtime. `PRESET_TABLE` in `theme.js` must match `ACCENT_PRESETS` in `cashew_integration/pwa.py`.
- **Auth**: same-origin session cookie + `window.boot.csrf_token`. No API keys in `localStorage`.
- **Build artifact**: `bench build --app cashew_integration` → `public/frontend/`. Commit `www/cashew.html` only; `public/frontend/` and `node_modules` are gitignored.
- **Icon regen**: after replacing `public/favicon.svg`, run `npx @vite-pwa/assets-generator --preset minimal-2023 public/favicon.svg` from `frontend/`, then `bench build`.
- **Responsive**: all surfaces must be mobile-responsive (v1 shipped with runs list + workspace + dashboard).

## Work Guidance

- New pages: add a Vue Router route in `src/router/` (or wherever routing is configured) and a corresponding component; follow the existing Shell layout pattern.
- New link pickers: always use `<LinkField :doctype="...">`, never `<Autocomplete reference_doctype="...">`.
- New aggregate data: add a whitelisted endpoint in `api.py` and call it once per surface.
- Design tokens and component mapping reference: `.fb/features/f010-cashew-frontend-spa/design_handoff_f010_cashew_spa/`.

## Verification

```
cd frontend && yarn build
```

Eslint and prettier run via `pre-commit` on JS/Vue files.
