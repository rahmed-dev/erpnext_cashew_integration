# Python App Package

## Purpose

Core Frappe app module for cashew_integration. Owns all server-side logic: DocType definitions, whitelisted API, import lifecycle, hooks, fixtures, and tests.

## Ownership

- DocTypes: `cashew_integration/doctype/` — Cashew Settings (Single), Cashew Import Run, Cashew Import Row, Cashew Account Mapping, Cashew Category Mapping
- Page: `page/cashew_row_explorer/` — Frappe Desk page for row-level diagnostics
- Workspace: `workspace/cashew_integration/` — Desk workspace JSON
- Fixtures: `fixtures/` — Desktop Icon fixture (`cashew_integration.json`) required for `/desk` tile
- Desktop Icon: `desktop_icon/cashew_integration.json` — fixture that makes the tile appear at `/desk`; without it the tile is absent even if all hooks are correct
- API: `api.py` — all whitelisted endpoints; every write endpoint must call `frappe.has_permission` at entry
- Setup wizard: `setup.py` — idempotent CoA find/create + settings seeding; callable from bench console or via `api.setup_from_csv`
- Install hook: `install.py` — `after_install`
- PWA renderer: `pwa.py` — `CashewPWAFile` page renderer serving `sw.js` (static) and `manifest.webmanifest` (dynamic, reads `Cashew Settings.accent_color`)
- Tests: `tests/` — `test_parser.py`, `test_mapping.py`, `test_integration.py`, `test_sqlite_import.py`; doctype test: `doctype/cashew_import_run/test_cashew_import_run.py`

## Local Contracts

- `hooks.py` `website_route_rules` is appended by `bench add-spa`; do not reassign the variable — Python last-assignment-wins would shadow the SPA routes. The PWA rules (`/cashew/sw.js`, `/cashew/manifest.webmanifest`) must precede the SPA catch-all.
- `Cashew Settings.accent_color` drives `manifest.webmanifest` `theme_color` at request time. The `ACCENT_PRESETS` dict in `pwa.py` must mirror `frontend/src/theme.js` `PRESET_TABLE`.
- `source_hash` (SHA-256 of company + account + date + amount + category) is the idempotency key — `idempotency.py` gates all re-imports.
- All DocType JSON files are the schema source of truth; never edit them through the Frappe UI without exporting back to `doctype/`.

## Work Guidance

- New whitelisted endpoints go in `api.py`; always call `frappe.has_permission(doctype, ptype, doc=...)` at the top.
- New importer logic belongs in `importer/`; see child AGENTS.md for pipeline module contracts.
- Fixtures exported via `bench export-fixtures` — check `hooks.py` `fixtures` list before adding.
- Icon SVGs live in `public/images/`; PWA PNGs regenerated with `@vite-pwa/assets-generator --preset minimal-2023 public/favicon.svg` from the `frontend/` dir, then `bench build --app cashew_integration`.

## Verification

```
bench run-tests --app cashew_integration
pre-commit run --all-files
```

## Child DOX Index

- [`importer/AGENTS.md`](importer/AGENTS.md) — import pipeline modules: parser, mapping, validation, idempotency, posting, worker, diagnostics, sqlite_reader
