# Cashew Integration

A Frappe/ERPNext v16 app that imports transactions from the [Cashew](https://cashewapp.web.app/) personal finance app into ERPNext as Sales Invoices, Purchase Invoices, and Journal Entries.

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app cashew_integration
```

On install, the app automatically seeds **Cashew Settings** with default account and category mappings derived from a real Cashew export (4 accounts, 35 categories). If no Chart of Accounts exists yet, seeding is skipped gracefully and can be re-run later:

```python
# bench console
from cashew_integration.setup import run_setup
run_setup()
```

---

## DocTypes

### Cashew Settings _(Single)_

Global configuration for the integration. Configured once per site.

| Field | Purpose |
|---|---|
| Company | Default company for all imports |
| Cashew Account Mapping | Maps Cashew account names → ERPNext Cash/Bank accounts |
| Cashew Category Mapping | Maps Cashew category + subcategory → ERPNext income/expense accounts |

The Setup Wizard (`api.setup_from_csv`) can re-seed these mappings from a fresh Cashew CSV export at any time. System Manager only.

---

### Cashew Import Run

One document per import batch. Tracks the full lifecycle from CSV upload to ERP posting.

**Key fields:**

| Field | Purpose |
|---|---|
| Company | Company to post under |
| Source CSV File | Attached Cashew CSV export |
| Status | Current lifecycle stage (see below) |
| Default Customer | Fallback customer for income rows without a party |
| Default Supplier | Fallback supplier for expense rows without a party |
| Balance Adjustment Account | Account used for Transfer/Balance Correction JEs |
| JV Rounding Tolerance | Max rounding difference allowed when balancing a JE |
| rows_total / rows_valid / rows_failed / rows_skipped / rows_posted | Live counters |
| queued_job_id | RQ job ID (set at queue time) |
| started_on / finished_on | Worker timestamps |
| diagnostics_file | Auto-generated CSV with per-row outcome after completion |

---

### Cashew Import Row _(Child of Cashew Import Run)_

One row per transaction in the CSV. Populated during Parse & Preview.

**Key fields:**

| Field | Purpose |
|---|---|
| row_idx | Original CSV row order |
| source_hash | SHA-256 of (company + account + date + amount + category) — used for idempotency |
| txn_date | Transaction date |
| raw_amount | Amount in source currency (negative = expense) |
| source_currency / company_currency | Currencies involved |
| exchange_rate / base_amount | Filled during Validate Import |
| txn_type | Income / Expense / Transfer |
| category / sub_category | From Cashew CSV |
| resolved_route | How the row will be posted: `Sales Invoice`, `Purchase Invoice`, `Journal Entry` |
| resolved_account | Mapped income/expense account |
| resolved_erp_account | Mapped Cash/Bank account |
| resolved_party / resolved_party_type | Customer or Supplier linked to this row |
| validation_status | Valid / Error / Skipped |
| validation_error_code | Machine-readable error code |
| validation_error_message | Human-readable explanation (also used for duplicate skip reason) |
| posted_doctype / posted_docname | SI / PI / JE created for this row (Dynamic Link) |
| is_duplicate | Set when idempotency guard finds a prior posting |
| revert_status | Reverted / Revert-Failed (set during revert) |
| revert_error | Error message if revert failed for this row |

---

## Import Lifecycle

```
Draft
  │
  ▼  [Parse & Preview button]
Parsed          CSV rows loaded into Import Rows child table. No ERP writes.
                Account/category mappings applied. Basic validation flags
                unmapped accounts. Re-parseable at any time.
  │
  ▼  [Validate Import button]
  ├─ errors → stays Parsed
  │           msgprint shows: row error codes, config issues,
  │           missing Currency Exchange records, FX summary.
  └─ clean  →
Validated       Exchange rates fetched (ERPNext → online providers).
                Idempotency guard runs — already-posted rows marked Skipped
                with message "Duplicate — already posted as {doctype} {name}".
                Run-level config validated (balance account, party fields).
  │
  ▼  [Queue Run button + confirm dialog]
Queued          Async RQ job enqueued. Queue-time validation re-runs
                (race-condition safety). queued_job_id populated.
  │
  ▼  (RQ worker picks up)
Processing      Rows posted one-by-one. Progress counters update in real-time
                via 3-second polling (no page refresh needed).
                Transfer pairs coordinated: first leg parked until partner arrives.
  │
  ├─ all rows done → Completed
  ├─ partial failure → Failed      (posted rows still have docname links)
  └─ user clicks Cancel → Cancelled
  │
  ▼  [Revert Run button + confirm dialog]
    Available on: Completed / Failed / Cancelled / Revert-Failed
Reverting       Async revert worker cancels each SI/PI/JE.
                posted_docname cleared on success (so re-import works).
  │
  ├─ all reversed → Reverted
  └─ some failed → Revert-Failed  (Revert Run button stays — retry safe)
```

**Buttons by status:**

| Status | Buttons |
|---|---|
| Draft | Parse & Preview |
| Parsed | Parse & Preview, Validate Import |
| Validated | Parse & Preview, Queue Run |
| Queued / Processing | Cancel Import |
| Completed / Failed / Cancelled / Revert-Failed | Revert Run |

---

## How Rows Are Posted

| Resolved Route | Condition | ERP Document |
|---|---|---|
| Sales Invoice | income row with a Customer | SI with one line item |
| Purchase Invoice | expense row with a Supplier | PI with one line item |
| Journal Entry | transfer, balance correction, or no party | JE balancing cash account ↔ income/expense account |

> **Warning:** Sales Invoice and Purchase Invoice posting paths have **not been tested** and **may not work**. Only the Journal Entry path has been verified in production. SI/PI logic exists in `importer/posting.py` but likely requires adjustments (item, tax, account configuration) before it functions correctly. Use with caution.

Each posted document gets a `cashew_row_hash` custom field (the source_hash) — used by the secondary idempotency check to detect duplicates even if the Cashew Import Row record is gone.

---

## Idempotency

Re-importing the same CSV (or any CSV with overlapping transactions) is safe. The guard runs at **Validate Import** time and again in the worker:

1. **Primary check**: queries `Cashew Import Row` for matching `source_hash` + `company` where `posted_docname` is not null.
2. **Secondary check**: queries `cashew_row_hash` custom field on SI/PI/JE directly (catches docs posted outside of this app).

Duplicate rows are marked `Skipped` with a message pointing to the existing ERP document. After a successful revert, `posted_docname` is cleared and `docstatus=2` on the cancelled doc — both checks correctly treat the row as unposted, so re-import works cleanly.

---

## Exchange Rates

Multi-currency rows (source_currency ≠ company_currency) require a Currency Exchange record in ERPNext. The Validate Import step fetches rates in this order:

1. Existing `Currency Exchange` record for the exact date.
2. ERPNext's online rate provider (if configured).

If no rate is found, the row is marked `Error: EXCHANGE_RATE_MISSING` and the validation msgprint lists exactly which pairs and dates are missing. Create those records under **ERPNext → Accounting → Currency Exchange**, then click Validate Import again.

---

## Setup Wizard

Re-seed Cashew Settings at any time from a fresh CSV export:

```python
# bench console — uses packaged defaults (no file needed)
from cashew_integration.setup import run_setup
run_setup()

# or seed from a CSV file
csv_bytes = open("/path/to/export.csv", "rb").read()
from cashew_integration.setup import run_setup_from_csv
run_setup_from_csv(company="My Company", csv_bytes=csv_bytes)
```

Via API (System Manager only):

```
POST /api/method/cashew_integration.api.setup_from_csv
  file_url: /files/export.csv
  company:  My Company   (optional — auto-detected from Global Defaults)
```

Both are idempotent — already-mapped entries are skipped.

---

## Project Structure

```
cashew_integration/
  api.py                   Whitelisted API endpoints
  setup.py                 Setup wizard (CoA find/create + settings seeding)
  install.py               after_install hook
  importer/
    parser.py              CSV → normalised row dicts
    mapping.py             Account/category/party mapping + exchange rates
    validation.py          Row + run-level validation rules
    idempotency.py         Duplicate detection (source_hash based)
    posting.py             SI / PI / JE creation
    worker.py              Async RQ worker (import + revert)
    diagnostics.py         Post-run diagnostics CSV generation
  cashew_integration/
    doctype/
      cashew_import_run/   Parent run DocType
      cashew_import_row/   Child row DocType
```

---

## License

MIT
