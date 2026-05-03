# Story: loan-accounts-guard

As an accountant setting up loan tracking for the first time, when I try to save a Cashew Category Mapping as Loan Out or Loan In and my chart of accounts isn't ready (no account marked as Receivable / Payable), I get a clear error that tells me exactly what to fix in chart of accounts — instead of an empty dropdown, a generic "field required" message, or a cryptic class mismatch.

## Acceptance Criteria

- Saving a Cashew Category Mapping with `category_type=Loan Out`:
  - If no Account exists with `root_type=Asset`, `account_type=Receivable`, `is_group=0`, `disabled=0` → block save with: *"No Receivable account exists in your chart of accounts. Create or configure an Asset account with account_type=Receivable (e.g. 'Loan Receivable - <Co>') before mapping a Loan Out category. See: Setup → Chart of Accounts."*
  - If at least one such account exists but the user picked a different account → c001's existing class-mismatch error fires (more specific message). c008 does not double-fire.
- Same shape for `Loan In` with `root_type=Liability`, `account_type=Payable`, `is_group=0`, `disabled=0`.
- Income / Expense `category_type` → no c008 check; c001 predicate alone applies.
- Check runs at Cashew Category Mapping row validate (which runs during Cashew Settings save).
- Error is friendly + actionable: plain text, names the missing account_type, points to chart of accounts setup, doesn't prescribe exact account names.
- No effect on already-saved mappings until they are edited and re-saved.

status: approved
