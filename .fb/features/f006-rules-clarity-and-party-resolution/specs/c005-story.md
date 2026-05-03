# Story: validation-error-prefix

As an accountant looking at validation errors outside the row grid (in the diagnostics CSV download, in a hover tooltip, or pasted into a support ticket), I can tell at a glance which row each error belongs to without having to cross-reference the grid — because the error message itself starts with the row number.

## Acceptance Criteria

- Every validation error written to `validation_error_message` is prefixed with `[Row {row_idx}] ` (e.g. `[Row 17] No active Cashew Account Mapping for account 'Petty Cash'.`).
- The prefix is added at the point the message is set, not at display time — so the prefix is visible everywhere the message goes: Cashew Import Row form, in-grid hover, diagnostics CSV file, logs, and the Vue Row Explorer (c006) error modal.
- Errors raised on rows that have no `row_idx` yet (file-level pre-parse errors — encoding, missing required column, empty file) do NOT get the prefix; they're not row-scoped.
- The diagnostics CSV (`Cashew Import Run.diagnostics_file`) carries `row_idx` as a column. If it doesn't already, add it.
- `validation_error_code` field (existing) is not touched. Only the human-readable message changes shape.
- Existing tests asserting specific error message text are updated to expect the prefix; no new error codes introduced.

status: approved
