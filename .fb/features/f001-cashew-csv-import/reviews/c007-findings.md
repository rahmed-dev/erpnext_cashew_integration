## C007 Async Worker + Progress Polling — pass

Previous major finding resolved. `income_flag` is now persisted on `Cashew Import Row` (confirmed in DocType JSON), flows through `_dict_to_child` (not in skip set), is reconstructed by both `_child_to_dict` and `_row_to_dict` via meta fields, and the worker's swap guard at line 112 operates correctly.

### Critical
- None.

### Major
- None.

### Minor
- None.
