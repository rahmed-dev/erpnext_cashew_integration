# Story: vue-row-explorer-page

As an accountant auditing or fixing a 500-row import, I open the Row Explorer for a run, switch between purpose-built column presets to keep the grid scannable, see colored status pills at a glance, fix party issues inline or via a modal that opens scoped to the actual error, and bulk-set party on a filtered subset when the same correction applies to many rows — without ever touching the source CSV or the heavy Import Run form.

## Acceptance Criteria

- Page mounts at `/app/cashew-row-explorer/<run-name>`; visible to roles that already see Cashew Import Run (Accountant, System Manager).
- Five column presets (radio toggle in toolbar):
  - **Compact** — `row_idx`, `txn_date`, `raw_amount`, `currency`, `txn_type`, `validation_status`.
  - **Resolution** — `row_idx`, `raw_account → resolved_erp_account`, `category → resolved_account`, `txn_type`, `resolved_route`, `resolved_party_type`, `resolved_party`.
  - **Validation** — `row_idx`, `txn_type`, `validation_status`, `validation_error_code`, `validation_error_message` (truncated + click-to-expand).
  - **Posted** — `row_idx`, `txn_date`, `raw_amount`, `currency`, `txn_type`, `posted_doctype`, `posted_docname` (link to ERP doc), `posted_gl_date`.
  - **Loans-and-Parties** — `row_idx`, `txn_type` (filtered to Loan Receivable / Loan Payable / Income+requires_party / Expense+requires_party only), `resolved_account`, `resolved_party_type`, `resolved_party`, `title`, `sub_category`, `note` (Option A loan-details surface).
- Filter bar: by `txn_type`, `validation_status`, posted-flag, has-error flag, free-text search across `title` / `note` / `category`. Multi-select where sensible. Filters compose with column presets.
- Status pills with color: Valid (green), Error (red), Skipped (gray), Posted (blue), Reverted (amber). Replace raw text wherever `validation_status` shows.
- Inline party edit on Loans-and-Parties + Resolution presets:
  - `resolved_party` cell becomes a Frappe Link control on click, pre-filtered to `resolved_party_type` (Customer if Loan Receivable or Income; Supplier if Loan Payable or Expense).
  - Save commits via whitelisted backend API; row re-validates on return; status pill updates without page reload.
- Fix-action modal driven by `validation_error_code`:
  - `LOAN_PARTY_MISSING` / `PARTY_MISSING` → party picker pre-filtered.
  - `CATEGORY_NOT_MAPPED` → "Add to Cashew Category Mapping" link (deep-link to Cashew Settings with the missing category pre-filled) — read-only message, no inline fix.
  - `CATEGORY_ACCOUNT_CLASS_MISMATCH` → message + link to the offending Cashew Category Mapping row in Cashew Settings.
  - `EXTERNAL_ACCOUNT_NOT_MAPPED` / generic → message + acknowledgment button.
  - Modal closes → row re-validates → pill updates.
- Bulk party set:
  - Apply current filter, select all in result set, click "Set party for selected", pick party from pre-filtered picker, confirm.
  - Backend API mutates all in one call within a transaction; re-validates affected rows; refreshes display.
- Backend API (whitelisted on `cashew_integration.api`):
  - `row_explorer_load(run_name)` → `{ rows, counts, enums }`.
  - `row_explorer_set_party(run_name, row_indices, party_type, party)` → `{ updated, errors }`.
  - `row_explorer_revalidate(run_name, row_indices=None)`.
- Permissions enforced on the backend — API methods check user has read/write on Cashew Import Run before mutating any row.
- Page works on a run in any status; mutation API is gated to status ∈ `{Draft, Validated, Failed, Cancelled}` — no mutating a Processing run or one that's already Posted (would diverge from ERP doc).
- Loan rows surface a "Loan details" inline section (or expandable row) showing `title` + `sub_category` + `note` + party — user-chosen loan identifier convention per Option A.
- "Open in Row Explorer" button on the Cashew Import Run form (covered in c007) deep-links here.

status: approved
