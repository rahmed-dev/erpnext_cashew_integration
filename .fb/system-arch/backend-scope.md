# Backend Scope

## ERPNext Integration
This project extends ERPNext accounting flows rather than operating as a standalone Frappe data model.

- Income postings target `Sales Invoice`.
- Expense postings use a configurable threshold:
  - Above threshold -> `Purchase Invoice`
  - At or below threshold -> `Journal Entry`

## Processing and Reliability

- Import execution runs through background jobs (`frappe.enqueue`) with status polling.
- Validation blocks error rows from posting.
- Import runs must be idempotent at ERP side to prevent duplicate posting of the same Cashew transaction on retry/re-import.

## Diagnostics and Audit

- Persist each run in an Import Log DocType.
- Provide downloadable CSV diagnostics for row-level outcomes.

## Data Volume Assumption

- Expected file size: ~100-1000 rows per import.

## Category-to-Account Mapping

Cashew transactions use a mapping table as default, with preview-time accountant override.

- Primary key from Cashew side: category (and optionally sub-category if present).
- Mapping output: default ERP account and posting hints used by the importer.
- Preview step allows accountant to override account/posting decision before queueing import.
- Missing mapping: row is marked as validation error; user can either set mapping table entry or apply explicit preview override based on final UI guardrails.

This balances deterministic defaults with practical exception handling.
