# Story: posting-loan-handler

As an accountant, when I queue an import run that contains loan transactions, each loan row posts to the ERP as a single Journal Entry that lands on the right party-tracked balance-sheet account, with the correct party attached to the receivable / payable line — so the loan appears in standard ERPNext Accounts Receivable / Payable reports filtered by party, and the cash account reflects the real movement.

## Acceptance Criteria

- A row with `txn_type=Loan Receivable` and `income_flag=false` (lent, money out) posts a JE with:
  - DR Loan Receivable account (`party_type=Customer`, `party=resolved_party`)
  - CR Cashew cash account (`resolved_erp_account`)
  Both legs in row currency. `base_amount` per leg in company currency via existing f001 exchange-rate logic.
- A row with `txn_type=Loan Receivable` and `income_flag=true` (repayment received) posts the reverse:
  - DR Cashew cash account
  - CR Loan Receivable account (`party_type=Customer`, `party=resolved_party`)
- A row with `txn_type=Loan Payable` and `income_flag=true` (borrowed, money in) posts:
  - DR Cashew cash account
  - CR Loan Payable account (`party_type=Supplier`, `party=resolved_party`)
- A row with `txn_type=Loan Payable` and `income_flag=false` (loan paid back) posts:
  - DR Loan Payable account (`party_type=Supplier`, `party=resolved_party`)
  - CR Cashew cash account
- Multi-currency: row currency may differ from company currency. JE per-line uses row currency + per-line exchange_rate; base totals balance in company currency within the run's `je_rounding_tolerance`. Same logic path as existing Income/Expense JE.
- Party always lands on the receivable/payable line (not the cash line), per ERPNext's expectation that party-tracked accounts carry party on the GL entry.
- `posted_doctype="Journal Entry"` and `posted_docname=<JE name>` are written back to the row on success — same shape as existing routes, consumed by f004 revert.
- JE references the source via Cashew Import Run name + row_idx (cheque_no / user_remark per existing convention).
- Failures: ERP doc-creation errors land on the row's `validation_error_message` via the c005 helper, with row_idx prefix. `posted_doctype` / `posted_docname` stay null. Run continues to next row.
- f004 revert paths work on Loan Receivable JE / Loan Payable JE the same way as on Income/Expense JE — `doc.cancel()` flips the loan-account entries; party reports update accordingly.

status: approved
