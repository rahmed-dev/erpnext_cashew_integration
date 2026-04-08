## Test Suite Review — C003 Mapping Tests (`test_mapping.py`) — pass

Re-review after dev re-engagement confirms prior findings are resolved.

### Critical
- None.

### Major
- None.

### Minor
- None.

### Verification Notes
- Positive ERP-rate path is now covered with a concrete assertion on both `exchange_rate` and recalculated `base_amount`.
- Inactive mapping row filtering is now explicitly tested for both account and category maps.
- Unresolved category behavior is now covered with explicit assertions that mapping-time leaves route/account unset and keeps the row diagnosable for queue-time handling.
