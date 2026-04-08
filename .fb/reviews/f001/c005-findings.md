## C005 Posting Engine (SI / PI / JE / Transfer JV / External Transfer JE / Adjustment JE) — fail

Previous two findings (txn_date for rate lookup; transfer label extraction) are resolved. One new major finding identified.

### Critical
- None.

### Major
- [`cashew_integration/importer/posting.py:301`] `_post_external_transfer_je` hardcodes `"multi_currency": 0` regardless of source currency. For foreign-currency external transfers (e.g., a USD account to an external), ERPNext receives `multi_currency=0` while `account_currency=USD` is set on the account lines — this produces silently wrong base-currency accounting or a submit-time rejection. Compare `_post_adjustment_je` (line 339) and `_post_journal_entry` (line 122) which both compute dynamically. → Replace the literal `0` with `multi_curr = 1 if src_cur != cmp_cur else 0` and use `multi_curr` in the doc dict.

### Minor
- [`cashew_integration/importer/posting.py:283–287`] `_post_external_transfer_je` duplicates the `Transferred Balance` note regex inline instead of calling `_extract_transfer_labels`. → Replace with `src_label, dst_label = _extract_transfer_labels(note, row["raw_account"], "External")`.
