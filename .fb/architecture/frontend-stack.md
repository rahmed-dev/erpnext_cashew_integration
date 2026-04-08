# Frontend Stack

## Decision
Use standard Frappe Desk form/list experience for import operations (no standalone Vue SPA for f001).

## Why

- Primary user is Accountant working inside ERPNext Desk.
- Import flow is operational and form-driven (upload -> validate -> queue -> monitor -> download diagnostics).
- Desk-native implementation minimizes delivery risk and training overhead.

## Scope for f001

- Import DocType/Form for file upload and run controls.
- Preview step for default-mapped rows with accountant override on exceptions.
- Status polling view for background job progress.
- Linked Import Log with downloadable diagnostics CSV.

## Future Direction

If f002 API sync introduces broader operational dashboards or exception worklists, reassess whether a lightweight portal or SPA adds value.
