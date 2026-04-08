## Test Suite Review — Posting/Flow Integration Tests (`test_integration.py`) — pass

Re-review after dev re-engagement confirms prior fail findings are resolved.

### Critical
- None.

### Major
- None.

### Minor
- None.

### Verification Notes
- Fixture now covers all six posting routes in one suite: Sales Invoice, Purchase Invoice, Journal Entry, Transfer JV, External Transfer JE, and Adjustment JE.
- Per-route tests were added with submitted-document assertions and run-linkage checks.
- Auto-settlement Payment Entry behavior is now verified for both SI and PI paths.
- Mixed-route `_process()` test now validates end-to-end behavior without pre-filtering to a single route.
- Row classification smoke test was upgraded to exact expected `txn_type` assertions per `row_idx`.
- External transfer multi-currency regression test exists and asserts `multi_currency` for same-currency vs foreign-currency source rows.
