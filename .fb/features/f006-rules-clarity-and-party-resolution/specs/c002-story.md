# Story: parser-loan-routing

As an accountant importing a CSV that mixes income, expense, and loan rows, each row is automatically classified into the right transaction type at parse time based on the category I configured in Cashew Settings — so I don't have to touch each row to tell the system "this is a loan disbursement, that is a loan repayment". The CSV direction (money in vs money out) plus the `category_type` I set on the Cashew Category Mapping gives the system everything it needs to pick the right posting route.

## Acceptance Criteria

- Rows whose category resolves to a Cashew Category Mapping with `category_type=Income` → `txn_type=Income` (existing behavior preserved).
- Rows whose category resolves to `category_type=Expense` → `txn_type=Expense` (existing behavior preserved).
- Rows whose category resolves to `category_type=Loan Out` → `txn_type=Loan Receivable`, `resolved_route=Loan Receivable JE`, regardless of `income_flag` direction (lent vs repayment-received both hit the receivable account).
- Rows whose category resolves to `category_type=Loan In` → `txn_type=Loan Payable`, `resolved_route=Loan Payable JE`, regardless of `income_flag` direction.
- Transfer-family rows (category in `{Balance Transfer, Balance Correction}`) classify exactly as today — Transfer / External Transfer / Adjustment — unchanged.
- A row whose category isn't in Cashew Category Mapping at all → existing validation error stands (CATEGORY_NOT_MAPPED at validate step). Parser doesn't crash, doesn't synthesize a `txn_type`.
- Income/Expense `resolved_route` continues to be set by existing logic (SI / PI / JE per posting threshold) — c002 doesn't touch that path.

status: approved
