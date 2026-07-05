# c005 — SPA SQLite upload surface

> Feature: f011 Cashew SQL (SQLite) Import
> Built on `arch/decisions.md`: *Ingestion Strategy — Add Alongside CSV*,
> *Import Scope — User-Chosen Date Window*, *SPA SQLite Upload Surface — in scope*.
> Depends on c002 (doctype fields + `parse_and_preview` dispatch must exist first).

## Overview

Without this component the SQL path is **Desk-form only** — the `/cashew` SPA upload flow
(`run-workspace/upload/`) is hardwired to CSV. This makes the SPA able to create a
`source_type=SQLite` run: adds a CSV/SQLite toggle, the optional date-window inputs, widens
the file dropzone to accept `.sql/.sqlite/.db`, and threads the three new fields through run
creation + field-persist. Everything after Parse (preview, workbench, post) is already
format-agnostic and reused with zero change.

Secondary: a small `source_type` badge on the run list + run header so an operator sees which
path a run used.

## Component detail

- **id:** c005
- **name:** spa-sqlite-upload-surface
- **type:** SPA (Vue) — `frontend/src/components/run-workspace/upload/` + `sections/UploadSection.vue`
- **depends_on:** [c002] — needs `source_type` / `import_from_date` / `import_to_date` on
  `Cashew Import Run` and the `parse_and_preview` SQLite branch. (c002 → c001 transitively.)

## UI / behavior changes

### `sections/UploadSection.vue` (primary)

- **`form` reactive** gains three keys:
  - `source_type` — default `props.doc?.source_type || 'CSV'`
  - `import_from_date` — default `props.doc?.import_from_date || null`
  - `import_to_date` — default `props.doc?.import_to_date || null`
- **Source-type toggle** above the file field. Prefer a frappe-ui control (segmented
  `<Button>` group or `<FormControl type="select">`) per the SPA design philosophy — no native
  `<select>`. Options: `CSV`, `SQLite`. Default `CSV`.
- **Date-window block**, rendered only when `form.source_type === 'SQLite'` (`v-if`). Two
  optional date inputs (`<FormControl type="date">` / frappe-ui `<DatePicker>`) bound to
  `import_from_date` / `import_to_date`. Label them "From date (optional)" / "To date
  (optional)" with helper "Blank = import whole backup." The Desk `depends_on` hides these on
  the form; the SPA must gate them with its own `v-if` (depends_on does not reach the SPA).
- **Dropzone** receives `:source-type="form.source_type"` (see CsvDropzone changes) so it
  widens accepted extensions + relabels.
- **`ensureRunExists()`** doc payload adds `source_type`, and — when SQLite — `import_from_date`
  and `import_to_date` (send `null`, not `undefined`, when blank).
- **`persistFieldChanges()`** field loop array adds `source_type`, `import_from_date`,
  `import_to_date` (the diff-and-`set_value` path already clears blanks via `?? ''`).
- **`canParse`** unchanged (company + file). Add a client guard: when SQLite and both dates set
  and `from > to`, disable Parse and show an inline error. This mirrors the c002 server guard —
  the server stays authoritative; this is fail-early UX only.
- **Copy:** header "upload the Cashew CSV export" → path-aware ("Cashew CSV export" vs "Cashew
  SQLite backup (.sql)"). Success `toast.success('CSV parsed.')` → generic `'Parsed.'` (or
  path-aware).

### `upload/CsvDropzone.vue` (widen; keep filename to avoid churn)

- Add prop `source_type` (default `'CSV'`).
- **Accept:** when SQLite, widen the picker `accept` to include `.sql,.sqlite,.db`
  (SQLite has no reliable MIME — add `application/x-sqlite3`, `application/vnd.sqlite3`
  best-effort but **validate by file extension**, not MIME). CSV path keeps today's `ACCEPT`.
- **Copy:** "CSV up to 50 MB" and the `'CSV must be under 50 MB.'` error → path-aware
  ("SQLite backup" / generic "File"). `MAX_BYTES` 50 MB stays (553-txn DB is tiny); note where
  to bump if a larger backup ever fails.
- Upload mechanics (`upload_file`, private, CSRF) unchanged — it already returns a `file_url`
  the run stores in `source_file`; the reader (c001) opens whatever bytes are attached.

### `source_type` badge (secondary, minor)

- Run list (`imports-list/RunCard.vue` / `RunRow.vue`) and `run-workspace/RunHeader.vue`:
  render a `rounded-full` pill showing `CSV` / `SQLite` from `source_type`. Add `source_type`
  to the `fields` array of the existing `frappe.client.get_list` read that feeds the list —
  no new endpoint.

## API discipline (binding — see app CLAUDE.md)

- **Writes stay on the existing core handlers** the upload flow already uses:
  `frappe.client.insert` (run create) and `frappe.client.set_value` (field persist), then the
  existing `cashew_integration.api.parse_and_preview`. `source_type` + the two dates are plain
  doc fields — **no new whitelisted endpoint** (rule 3 / 4 untouched).
- **Reads stay on `frappe.client.get_list`** with `source_type` added to `fields` (rule 1).
- **Controls** use frappe-ui, not native `<select>`/`<input>` (design philosophy #5).

## Data flow

```mermaid
flowchart TD
    A[UploadSection: pick source_type] --> B{CSV or SQLite?}
    B -- SQLite --> C[show date-window inputs + widen dropzone accept]
    B -- CSV --> D[today's flow, unchanged]
    C --> E[client guard: from > to disables Parse]
    E --> F[ensureRunExists / persistFieldChanges include source_type + dates]
    D --> F
    F --> G[parse_and_preview run_name  (c002 dispatch)]
    G --> H[preview + workbench + post — UNCHANGED]
```

## Permissions

Unchanged. Run create/patch already go through `frappe.client.*` (DocPerm enforced); the new
fields inherit `Cashew Import Run` field perms. No new role. `/cashew` role gate (System
Manager / Accounts Manager) unchanged.

## Notes / gotchas

- **Date format:** frappe stores Date as `'YYYY-MM-DD'` strings. Ensure the picker emits that,
  not a JS `Date` object, to `insert`/`set_value`.
- **Default `CSV`** → a user who touches nothing gets exactly today's SPA behavior. Purely
  additive.
- **Switching SQLite→CSV:** leave any entered dates as-is (CSV path ignores them; Desk hides
  them). Do not force-clear.
- **`.sql` is the whole DB** — the date-window inputs are the operator's per-run scope control
  (arch decision *Import Scope*); this is the SPA surface for that decision.
- This component does **not** change the parity/posting gate (c003) — it only feeds the same
  pipeline through the SPA.

status: draft-for-dev
