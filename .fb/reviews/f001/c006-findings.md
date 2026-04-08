## C006 Idempotency Guard — pass with notes

### Critical
- None.

### Major
- None.

### Minor
- [`cashew_integration/importer/idempotency.py`] Unused local `all_hashes` is built from `raw_amount` instead of `source_hash` and never consumed. This is misleading and increases maintenance risk. -> Remove the dead variable or replace with a correctly used `source_hash` set.
