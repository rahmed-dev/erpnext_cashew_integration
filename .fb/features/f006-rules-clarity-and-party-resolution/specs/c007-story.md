# Story: import-run-form-slim

As an accountant opening the Cashew Import Run form, I get a prominent "Open in Row Explorer" button that takes me to the Vue page for the heavy work — verifying mappings, fixing parties, auditing posted docs. The existing `import_rows` table on the form stays exactly as it is today; I can still glance at it for quick in-form peeks. Two surfaces, two purposes: form for run-level overview + actions, Explorer for row-level work.

## Acceptance Criteria

- A prominent "Open in Row Explorer" button appears on the Cashew Import Run form. Visible whenever the run has any rows. Clicking navigates to `/app/cashew-row-explorer/<run-name>`.
- Button placement: form's primary-action area (via `frm.add_custom_button` or page primary-action) so it sits alongside existing run-level actions (Validate Import, Queue Run, etc.).
- `import_rows` child table grid stays exactly as today — same columns, same in-grid edit behavior, same `in_list_view` fields. No grid layout change, no field hiding.
- `default_customer` / `default_supplier` remain hidden (set by c001); c007 verifies layout — no separate change here.
- Run-level fields and existing actions (Validate Import, Queue Run, Cancel Run, Revert Run, Repair) all unchanged.
- Mobile / narrow viewport: button is still tappable.

status: approved
