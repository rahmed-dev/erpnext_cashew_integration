# Story: schema-loan-and-category-type

As an accountant configuring Cashew categories, I can tag each category as Income, Expense, Loan Receivable, or Loan Payable, and the import system will treat that tag as authoritative — routing rows to the right posting path AND rejecting rows whose linked account doesn't match the type — so loans stop polluting my P&L and category misconfigurations are caught at validate time instead of producing wrong GL entries.

## Acceptance Criteria

- Every Cashew Category Mapping row carries a `category_type` tag (Income / Expense / Loan Receivable / Loan Payable).
- The import engine uses `category_type` as the routing signal for ALL transaction kinds:
  - Income → SI/JE income path
  - Expense → PI/JE expense path
  - Loan Receivable / Loan Payable → loan JE path
- Account-class consistency is enforced **both** at Category Mapping save **and** at `validate_import` time (defense in depth — catches setup errors early; catches account-class drift on existing mappings). Examples that must error:
  - Expense-typed category linked to an Income account
  - Income-typed category linked to an Expense account
  - Loan-typed category linked to a P&L account (not Asset/Liability)
- The legacy run-level `default_customer` / `default_supplier` inputs no longer appear on the Cashew Import Run form (party is set per-row in the Row Explorer — c006).
- Existing categories and existing import-run records keep working — no data loss, no broken historical runs.

status: approved
