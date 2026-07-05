# c002 — source_type discriminator + parse_and_preview branch

> Feature: f011 Cashew SQL (SQLite) Import
> Built on `arch/decisions.md`: *Reuse the Entire Pipeline — Only the Reader Is New*,
> *Ingestion Strategy — Add Alongside CSV*.
> Detail source: `arch/sql-import-plan.md` §1, §6. User decision 2026-07-04: date window.

## Overview

The data-model + seam change that lets a `Cashew Import Run` choose the SQL path. Adds a
`source_type` Select to the run, two optional date-window fields, allows `.sql/.sqlite/.db`
uploads, and replaces the single CSV-specific line in `api.parse_and_preview` with a
dispatch. Everything downstream of that line (`apply_mappings` onward) is untouched.

## Component detail

- **id:** c002
- **name:** source-type-discriminator
- **type:** doctype-fields + api-seam-change (`Cashew Import Run` JSON + `api.py`)
- **depends_on:** [c001] — the branch calls `read_sqlite(...)`; its signature must exist.

### Data model changes — `Cashew Import Run`

| fieldname | fieldtype | required | default | description |
|---|---|---|---|---|
| `source_type` | Select (`CSV`\n`SQLite`) | yes | `CSV` | Which reader ingests `source_file`. Drives the §1 branch; lets SPA/Desk show the path a run used. |
| `import_from_date` | Date | no | — | SQLite only. Inclusive lower bound (site-local date). Blank = no lower bound. |
| `import_to_date` | Date | no | — | SQLite only. Inclusive upper bound (site-local date). Blank = no upper bound. |

- Place `source_type` above `source_file`; place the two date fields after it. Use
  `depends_on: eval:doc.source_type=='SQLite'` on both date fields so they only show for the
  SQL path (CSV runs ignore them entirely).
- `source_file`: allow `.sql`, `.sqlite`, `.db` in addition to `.csv`. If an attach-type
  validation restricts extensions today, widen it; otherwise no change needed. Do not force
  the extension — validate readability at parse time instead (a wrong file surfaces as a
  reader error, not a silent pass).
- No change to `Cashew Import Row` — reused as-is.

### Seam change — `api.parse_and_preview`

Replace the single CSV-specific line (`rows = parse_csv(file_content, company_currency)`,
~line 127) with a dispatch on `source_type`:

```python
if run.source_type == "SQLite":
    rows = read_sqlite(
        file_content, company_currency,
        from_date=run.import_from_date, to_date=run.import_to_date,
    )
else:
    rows = parse_csv(file_content, company_currency)
```

- `read_sqlite` returns the same `list[dict]` shape `parse_csv` returns — **line 130
  (`apply_mappings`) onward is unchanged**, including `_compute_txn_period` (period stays
  derived from `min/max` of the imported rows, so it auto-narrows to the chosen window).
- Import `read_sqlite` from `cashew_integration.importer.sqlite_reader`.
- Surface a `from_date > to_date` guard error from here (or let the reader raise and let it
  propagate) as a clean `frappe.throw`, not a stack trace.

### Endpoints

No new whitelisted endpoint. `parse_and_preview` keeps its existing signature and
permission gate; only its internal dispatch changes.

## Data flow

```mermaid
flowchart TD
    A[User sets source_type + attaches file + optional window] --> B[parse_and_preview run_name]
    B --> C[_read_attached_file source_file]
    C --> D{run.source_type}
    D -- SQLite --> E[read_sqlite content, ccy, from_date, to_date  (c001)]
    D -- CSV --> F[parse_csv content, ccy]
    E --> G[apply_mappings — UNCHANGED]
    F --> G
    G --> H[persist Cashew Import Row children]
    H --> I[_compute_txn_period min/max -> period_start/end]
    I --> J[status = Parsed, save, commit]
```

## Permissions

Unchanged. `parse_and_preview` already checks permission on the `Cashew Import Run`.
`source_type`/date fields inherit the DocType's field-level perms — no new role.

## Notes / gotchas

- Frappe v16: adding Select/Date fields to an existing DocType JSON needs
  `bench --site <site> migrate` to apply. New field order requires the JSON `field_order`
  array updated too, not just the `fields` list.
- Default `source_type=CSV` keeps every existing run and the f001/f010 flows behaving
  exactly as before — this change is additive.
- The SPA/Desk may later show a badge for `source_type`; not required by this component.

status: draft-for-dev
