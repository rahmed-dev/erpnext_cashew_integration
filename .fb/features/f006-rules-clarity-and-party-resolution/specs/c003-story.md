# Story: mapping-engine-simplification

As an accountant using the simplified mapping engine, when the engine processes my parsed rows it resolves the ERP account each row should post to from my Cashew Settings — but it stops trying to guess the party. Instead, it tells me when a row needs a party and what kind of party (Customer / Supplier) so I can set it manually in the Row Explorer before posting.

## Acceptance Criteria

- Account resolution unchanged for non-loan rows: Income/Expense rows get `resolved_account` from the Cashew Category Mapping `default_account` (existing behavior); Transfer / External Transfer / Adjustment rows bypass Cashew Category Mapping (existing behavior).
- Loan rows (`txn_type ∈ {Loan Receivable, Loan Payable}`, set by c002): engine sets `resolved_account` from the same Category Mapping `default_account` — which by c001 contract points to the shared Loan Receivable / Loan Payable account (Decision 4).
- Party auto-resolution is removed: engine no longer reads `default_customer` / `default_supplier` on the run, no longer derives `party_source`. Whatever the user sets per-row stands.
- Party-required validation fires at validate_import per row:
  - `txn_type=Loan Receivable` — requires `party_type=Customer` + party set. Error code: `LOAN_PARTY_MISSING`.
  - `txn_type=Loan Payable` — requires `party_type=Supplier` + party set. Error code: `LOAN_PARTY_MISSING`.
  - `txn_type=Income` with category `requires_party=1` — requires `party_type=Customer` + party set. Error code: `PARTY_MISSING` (existing).
  - `txn_type=Expense` with category `requires_party=1` — requires `party_type=Supplier` + party set. Error code: `PARTY_MISSING` (existing).
  - Transfer / External Transfer / Adjustment — no party check.
- `party_source` field stays on Cashew Import Row schema for backwards compat with f004 revert (don't drop columns); engine no longer writes to it. Always null on new runs.
- Run-level `default_customer` / `default_supplier` fields stay nullable in DB (c001 hide-only); engine doesn't read them. f004 revert paths reading them on old run records continue to work.
- Existing tests that asserted party fallback to run-defaults are updated — engine no longer auto-fills from run defaults.

status: approved
