# Import Pipeline

## Purpose

All server-side import logic: parse Cashew exports (CSV and SQLite), map accounts/categories/parties, validate rows, guard idempotency, and post ERPNext documents.

## Ownership

| Module | Responsibility |
|---|---|
| `parser.py` | CSV bytes → normalised row dicts |
| `sqlite_reader.py` | Cashew SQLite DB → normalised row dicts (f011); hash-parity with CSV path; FK pairing for transfers |
| `mapping.py` | Account/category/party mapping + exchange rate resolution |
| `validation.py` | Row-level and run-level validation rules; populates `validation_status` / `validation_error_code` |
| `idempotency.py` | Duplicate detection via `source_hash` (SHA-256 of company + account + date + amount + category); gates all re-imports |
| `posting.py` | Creates Sales Invoice / Purchase Invoice / Journal Entry per resolved row |
| `worker.py` | Async RQ worker: orchestrates import and revert jobs; sets `queued_job_id`, `started_on`, `finished_on` |
| `diagnostics.py` | Post-run diagnostics CSV generation; writes `Cashew Import Run.diagnostics_file` |

## Local Contracts

- `sqlite_reader` output must be hash-identical to the CSV path for the same transaction — `source_hash` is the shared idempotency key across both import surfaces.
- `sqlite_reader` handles FK pairing: transfer transactions appear as two rows in the SQLite DB; the reader pairs them and emits a single Transfer row, matching CSV behavior.
- `source_type` field on `Cashew Import Run` distinguishes `CSV` from `SQLite`; the two surfaces are add-alongside (not mutually exclusive).
- `date_window` seam: `sqlite_reader` accepts start/end date filters; the worker passes them through unchanged.
- `mapping.py` exchange rates: resolved at validation time, stored on `Cashew Import Row.exchange_rate`; never re-fetched at post time.
- `posting.py` uses `resolved_route` on each row to determine SI / PI / JE; do not re-derive the route inside posting.
- Worker sets `Cashew Import Run.status` transitions; no other module may write status.

## Work Guidance

- New import surface (e.g. new file format) must output the same normalised row dict schema as `parser.py`; use `sqlite_reader.py` as the reference implementation.
- Any change to `source_hash` computation breaks idempotency for existing imports — treat as a breaking migration.
- Exchange rate failures are non-fatal at validation; rows get `validation_error_code = EXCHANGE_RATE_MISSING` and are skipped at post.

## Verification

```
bench run-tests --app cashew_integration --module cashew_integration.tests.test_parser
bench run-tests --app cashew_integration --module cashew_integration.tests.test_mapping
bench run-tests --app cashew_integration --module cashew_integration.tests.test_integration
bench run-tests --app cashew_integration --module cashew_integration.tests.test_sqlite_import
```
