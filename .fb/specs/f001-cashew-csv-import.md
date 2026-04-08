# F001 Technical Spec: Cashew CSV Import (v3)

## Scope

- Parse Cashew CSV (cash-basis source) and post accrual-compliant accounting entries in ERPNext.
- CSV import works directly from a fresh Cashew export — no manual file edits required.
- Support multi-currency rows (at least PKR and USD in the same file) with explicit conversion to company currency.
- Route by transaction type:
  - Income → `Sales Invoice`
  - Expense > threshold → `Purchase Invoice`
  - Expense ≤ threshold → `Journal Entry`
  - Balance Correction or Balance Transfer (paired internal transfer) → `Transfer Journal Entry`
  - Balance Correction or Balance Transfer (external-account orphan) → `External Transfer JE`
  - Balance Correction or Balance Transfer (solo adjustment) → `Adjustment JE` against `balance_adjustment_account`
- Provide preview overrides, async execution, diagnostics CSV, and idempotency.

## Architecture Constraints Referenced

- `architecture/decisions-log.md` — all decisions including Transfer JV, Cashew Account Mapping, Exchange Rate Source of Truth (2026-04-08)
- `architecture/backend-scope.md`
- `architecture/data-flow.md`
- `architecture/frontend-stack.md`

## Story Contract (Approved v3)

1. Upload and preview parsed rows with default mappings.
2. Override posting decision, account, or party per exception row before queueing.
3. Execute asynchronously with progress and diagnostics.
4. Guarantee idempotent re-run behavior.
5. Block only truly invalid rows; valid rows always proceed.
6. Post internal account transfers (paired Balance Correction) as Transfer JVs, including cross-currency.
7. Handle external-account and solo Balance Correction rows without blocking the import run.

## Component Order (Dependency Sequence)

1. **C001** — Data Model
2. **C002** — CSV Parser + Normalizer
3. **C003** — Mapping + Preview Override Engine
4. **C004** — Validation Engine
5. **C005** — Posting Engine (SI / PI / JE / Transfer JV / External Transfer JE / Adjustment JE)
6. **C006** — Idempotency Guard
7. **C007** — Async Worker + Progress Polling
8. **C008** — Diagnostics CSV
9. **C009** — Install-Time Setup

---

## C001 Data Model

### DocType: `Cashew Settings` (Single Document — system-wide configuration)

Non-submittable singleton. Accessed via `frappe.get_single("Cashew Settings")`.
No `company` field — configuration is global; company scoping happens at the run level.

Contains two child tables:

#### Child Table 1: `Cashew Account Mapping`

Maps each Cashew account name (from CSV `account` column) to an ERPNext GL account.
Includes both internal accounts (Petty Cash, NSave, Saving, Investment) and any external accounts
that appear only in transfer notes (e.g., Meezan Bank).

| Field | Type | Notes |
|-------|------|-------|
| `cashew_account_name` | Data | reqd; exact string from CSV `account` column or transfer note |
| `erp_account` | Link Account | reqd; target ERPNext GL account |
| `account_currency` | Link Currency | reqd; must match ERPNext account currency |
| `is_active` | Check | default 1 |

Unique key: `cashew_account_name`

#### Child Table 2: `Cashew Category Mapping`

Maps each Cashew category (and optional subcategory) to an ERPNext route and account.

| Field | Type | Notes |
|-------|------|-------|
| `cashew_category` | Data | reqd |
| `cashew_sub_category` | Data | optional |
| `default_route` | Select: Sales Invoice / Purchase Invoice / Journal Entry | reqd |
| `default_account` | Link Account | reqd |
| `is_active` | Check | default 1 |

Unique key: `(cashew_category, cashew_sub_category)`

---

### DocType: `Cashew Import Run`

Non-submittable. `company` is the only company-scoped field in the entire system.
Protected from deletion once `status != Draft` (controller-enforced).

| Field | Type | Notes |
|-------|------|-------|
| `name` | Autoname | |
| `company` | Link Company | reqd; all currency and account lookups use this company |
| `source_file` | Attach | reqd |
| `status` | Select: Draft / Validated / Queued / Processing / Completed / Failed | reqd, default Draft |
| `expense_threshold` | Currency | reqd; rows at or below this amount route to JE instead of PI |
| `default_customer` | Link Customer | optional; fallback customer for all SI rows without a per-row party override |
| `default_supplier` | Link Supplier | optional; fallback supplier for all PI rows without a per-row party override |
| `default_mode_of_payment` | Link Mode of Payment | reqd |
| `auto_settle_cash` | Check | default 1; Cashew records actual cash events so every SI/PI is already settled — Payment Entry is created automatically |
| `balance_adjustment_account` | Link Account | required when the file contains any solo Balance Correction / Balance Transfer rows (Adjustment type); validated at queue time |
| `je_rounding_tolerance` | Currency | default 0.01; max acceptable base-amount diff for cross-currency transfer JVs |
| `rows_total` | Int | read-only |
| `rows_valid` | Int | read-only |
| `rows_posted` | Int | read-only |
| `rows_failed` | Int | read-only |
| `rows_skipped` | Int | read-only; idempotency duplicates |
| `queued_job_id` | Data | read-only |
| `started_on` | Datetime | read-only |
| `finished_on` | Datetime | read-only |
| `diagnostics_file` | Attach | read-only; populated by C008 on completion |

---

### Child DocType: `Cashew Import Row`

Child of `Cashew Import Run`. Not directly accessible; only via parent form.

| Field | Type | Notes |
|-------|------|-------|
| `row_idx` | Int | reqd; 1-based position in source file |
| `source_hash` | Data | reqd, indexed; see C002 for algorithm |
| `raw_account` | Data | reqd; exact value from CSV `account` column |
| `txn_date` | Date | reqd |
| `month_key` | Data (YYYY-MM) | reqd; derived from `txn_date` |
| `raw_amount` | Currency | reqd; absolute value |
| `source_currency` | Link Currency | reqd |
| `company_currency` | Link Currency | reqd; derived from `run.company` at parse time |
| `exchange_rate` | Float | default null; 1 for same-currency; set by accountant or implied for transfers |
| `base_amount` | Currency | computed; in company currency; 0 while exchange_rate is null |
| `txn_type` | Select: Income / Expense / Transfer / External Transfer / Adjustment | reqd |
| `category` | Data | reqd |
| `sub_category` | Data | optional |
| `resolved_route` | Select: Sales Invoice / Purchase Invoice / Journal Entry / Transfer JV / External Transfer JE / Adjustment JE | |
| `resolved_account` | Link Account | destination income/expense account |
| `resolved_erp_account` | Link Account | cash source/destination from Cashew Account Mapping (row's own account) |
| `resolved_external_account` | Link Account | external partner account (External Transfer rows only) |
| `resolved_party` | Dynamic Link | |
| `resolved_party_type` | Select: Customer / Supplier / None | |
| `party_source` | Select: Preview Override / Run Default | |
| `title` | Data | trimmed CSV `title` value; empty string if blank |
| `note` | Small Text | trimmed CSV `note` value; preserves embedded newlines; empty string if blank |
| `raw_txn_time` | Time | time portion from CSV datetime; retained for transfer-pair sort order only; not shown in UI |
| `transfer_pair_row_idx` | Int | row_idx of the paired transfer leg (Transfer type only) |
| `item_label` | Data | `{category} \| {month_key}`; used as `item_name` on SI/PI item line |
| `validation_status` | Select: Valid / Error / Skipped | reqd |
| `validation_error_code` | Data | |
| `validation_error_message` | Small Text | |
| `posted_doctype` | Data | |
| `posted_docname` | Dynamic Link | |
| `posted_gl_date` | Date | |
| `is_duplicate` | Check | default 0; set by idempotency guard |

---

## C002 CSV Parser + Normalizer

### Exact Column Mapping

| CSV Header (exact) | Internal Field | Transformation |
|--------------------|----------------|----------------|
| `account` | `raw_account` | Trim whitespace |
| `amount` | `raw_amount` | `round(abs(float(value)), 2)`; see sign logic |
| `currency` | `source_currency` | Trim; validate against ERPNext Currency master |
| `title` | `title` | Trim; empty string if blank |
| `note` | `note` | Trim; preserve embedded newlines (quoted CSV field) |
| `date` | `txn_date` | Parse datetime, keep date only; see below |
| `income` | `income_flag` | Lowercase string; must be `"true"` or `"false"` |
| `type` | *(ignored)* | Ignored regardless of value; non-null logged in diagnostics |
| `category name` | `category` | Trim; case-preserved |
| `subcategory name` | `sub_category` | Trim; empty string if blank |
| `color` | *(ignored)* | |
| `icon` | *(ignored)* | |
| `emoji` | *(ignored)* | |
| `budget` | *(ignored)* | |
| `objective` | *(ignored)* | |

### Transaction Type Assignment

```python
TRANSFER_CATEGORIES = {"Balance Correction", "Balance Transfer"}

if category.strip() in TRANSFER_CATEGORIES:
    txn_type = "Transfer"   # temporary; overwritten to Transfer / External Transfer / Adjustment in classification pass
elif income_flag == "true":
    txn_type = "Income"
else:
    txn_type = "Expense"
```

Both `"Balance Correction"` and `"Balance Transfer"` enter the same pairing and classification pass.
The initial `txn_type = "Transfer"` is a temporary placeholder — the classification pass overwrites it
with the final value (`Transfer`, `External Transfer`, or `Adjustment`).
The original category string is preserved on `row.category` for diagnostics and audit.

Amount is always stored as absolute value regardless of CSV sign.

### Datetime Normalization

Input format: `YYYY-MM-DD HH:MM:SS.mmm` (e.g., `2026-04-08 20:27:31.000`)

```python
dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S.%f")
txn_date = dt.date()        # YYYY-MM-DD; time discarded for posting
raw_txn_time = dt.time()    # retained internally for transfer-pair sort order only
```

### Source Hash Algorithm

```python
import hashlib, json

payload = {
    "account":      raw_account.strip(),
    "amount":       str(round(abs(float(raw_csv_amount)), 10)),  # full precision in hash
    "currency":     currency.strip(),
    "date":         txn_date.isoformat(),          # YYYY-MM-DD
    "income":       income_flag.strip().lower(),
    "category":     category.strip(),
    "subcategory":  sub_category.strip() if sub_category else "",
    "title":        title.strip() if title else "",
    "note":         note.strip() if note else "",
}
source_hash = hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
```

### Balance Correction Classification Pass

Executed after all rows are parsed, before preview is shown.
Classifies every row with `txn_type == "Balance Correction"` (i.e., rows whose original
`category` is either `"Balance Correction"` or `"Balance Transfer"`) into one of four subtypes:

#### Step 1 — Note pattern detection

For each Balance Correction row, try the regex:
```
^Transferred Balance\n(.+)\s→\s(.+)$
```
- **Match** → note type = `paired_transfer`; extract `(transfer_source_name, transfer_dest_name)`
- **No match** → note type = `adjustment` (covers "Updated Total Balance\n...", empty notes, or any other format)

#### Step 2 — Pairing (paired_transfer rows only)

**Group key: `(note.strip(), txn_date.isoformat())`** — same note on different dates are independent pairs.

Within each group:
- Require exactly 2 rows: one `income_flag = "false"` (source leg) and one `income_flag = "true"` (destination leg).
- Valid pair: check whether the **partner account** (`transfer_source_name` or `transfer_dest_name`, whichever is not `raw_account`) exists in the set of `raw_account` values across the entire file.
  - **Partner exists in file** → `txn_type = "Transfer"`; set `transfer_pair_row_idx` on each row.
  - **Partner does NOT exist in file** → `txn_type = "External Transfer"`; set `resolved_external_account` from Cashew Account Mapping for the partner name.
- Group count ≠ 2 (and partner exists in file) → `validation_error_code = TRANSFER_PAIR_INCOMPLETE`; both rows blocked.

#### Step 3 — Adjustment rows

All Balance Correction / Balance Transfer rows with note type = `adjustment` get:
- `txn_type = "Adjustment"`
- `resolved_route = "Adjustment JE"`
- `validation_status = "Valid"`

These always post as an Adjustment JE. The `balance_adjustment_account` field on the run is required
when any Adjustment rows are present; missing it is a queue-time hard block (`RUN_CONFIG_MISSING`).

### File-Level Pre-validation (abort entire file on failure)

- All required column headers present (case-insensitive; abort with `FILE_MISSING_COLUMNS`)
- File encoding UTF-8 or UTF-8-BOM (abort with `FILE_ENCODING_ERROR`)
- At least one data row present (abort with `FILE_EMPTY`)

---

## C003 Mapping + Preview Override Engine

### Settings Lookup

All config lookups read from `Cashew Settings` (single document). No company filter on lookups.

### Cashew Account Mapping Lookup

Applied to **every row**. Lookup key: `cashew_account_name` (exact match on `row.raw_account`).

Stored as `resolved_erp_account`. Missing mapping → `validation_error_code = CASHEW_ACCOUNT_NOT_MAPPED`.

For External Transfer rows, also look up the partner account name (from transfer note):
- Found → `resolved_external_account`
- Not found → `validation_error_code = EXTERNAL_ACCOUNT_NOT_MAPPED`

### Category Mapping Lookup

For non-Transfer, non-Adjustment rows.

1. Try key `(category, sub_category)` (with sub_category if non-empty).
2. Fall back to `(category, "")` if step 1 misses.
3. If still no active mapping: `resolved_account = null`, `resolved_route = null`; row enters preview as unresolved.

Output: `resolved_account`, `resolved_route`.

### Exchange Rate Resolution

The ERP rate table is a **convenience default only** — the actual transacted rate is authoritative.

- Same currency (`source_currency == company_currency`): `exchange_rate = 1`. No lookup.
- Transfer / External Transfer rows: **do not look up ERP rate**. Implied rate computed at posting time (C005). Leave `exchange_rate = null`.
- Adjustment rows in foreign currency: treated the same as SI/PI/JE — ERP rate pre-fills; accountant confirms in preview; null at queue time is a hard block.
- All other foreign-currency rows (SI / PI / JE):
  1. Attempt ERP rate lookup for `(from=source_currency, to=company_currency, date=txn_date)`.
  2. Found → pre-fill `exchange_rate` as default suggestion.
  3. Not found → `exchange_rate = null`.
  4. The field is **editable in preview** — accountant confirms or replaces with actual transacted rate.

`base_amount = round(raw_amount * exchange_rate, 2)` when set; `0` while null.

A null `exchange_rate` on a non-Transfer foreign-currency row is **not a pre-preview error** — it becomes a hard block only at queue time.

### Party Resolution

No automatic mapping rules. Two-stage only:

1. **Preview override** — accountant sets `resolved_party` + `resolved_party_type` per row manually.
2. **Run default fallback** — if no per-row override:
   - SI rows: use `run.default_customer` (if set). `party_source = "Run Default"`.
   - PI rows: use `run.default_supplier` (if set). `party_source = "Run Default"`.
3. If neither override nor default is available for an SI/PI row → `validation_error_code = PARTY_UNRESOLVED` at queue time.

JE, Transfer JV, External Transfer JE, and Adjustment JE rows skip party resolution entirely.

### Preview Override Scope (per row)

| Override | Applies to |
|----------|-----------|
| `resolved_route` | Non-Transfer, non-Adjustment rows |
| `resolved_account` | All non-Transfer rows |
| `resolved_party` + `resolved_party_type` | SI / PI rows |
| `exchange_rate` | All foreign-currency non-Transfer rows |

Overrides persisted on row before queueing. Transfer rows shown read-only in preview.

---

## C004 Validation Rules

Per-row. Valid rows proceed even if others in the same run have errors.
Transfer pairs treated atomically: if either leg fails, both are blocked.

| Error Code | Trigger Condition | Gate |
|------------|-------------------|------|
| `MISSING_DATE` | `txn_date` null or unparseable | Pre-preview |
| `MISSING_AMOUNT` | Amount null, zero, or non-numeric | Pre-preview |
| `MISSING_CATEGORY` | `category` empty after trim | Pre-preview |
| `CASHEW_ACCOUNT_NOT_MAPPED` | No active account mapping for `raw_account` | Pre-preview |
| `EXTERNAL_ACCOUNT_NOT_MAPPED` | External transfer: partner account not in Cashew Account Mapping | Pre-preview |
| `TRANSFER_PAIR_INCOMPLETE` | Paired transfer note group has ≠ 2 rows (and partner account is in file) | Pre-preview |
| `MAPPING_NOT_FOUND` | No category mapping and no preview override (non-Transfer rows) | Queue time |
| `INVALID_ACCOUNT_TYPE` | `resolved_account` type incompatible with `resolved_route` | Queue time |
| `PARTY_UNRESOLVED` | SI/PI row: no per-row override and no run default set | Queue time |
| `EXCHANGE_RATE_MISSING` | SI / PI / JE / Adjustment JE row where `source_currency != company_currency` and `exchange_rate` is still null at queue time. **Does not apply to Transfer or External Transfer rows** — those use the implied rate computed from pair amounts at posting time. | Queue time |
| `EXCHANGE_RATE_INVALID` | SI / PI / JE / Adjustment JE row where `exchange_rate` is set but produces a non-finite, negative, or zero `base_amount`. Does not apply to Transfer rows. | Queue time |
| `TRANSFER_JV_IMBALANCE` | Cross-currency transfer pair: base-amount diff > `je_rounding_tolerance` | Posting time |
| `RUN_CONFIG_MISSING` | Required run-level setup absent at queue time (see Required Defaults Matrix) | Queue time |

---

## C005 Posting Engine

### Principle

Cashew rows represent cash-basis transaction evidence. ERPNext books are accrual-basis. Importer posts accrual-compliant source documents first; cash settlement is explicit and optional.

### Currency Handling

- Same currency: `exchange_rate = 1`, `base_amount = round(abs(raw_amount), 2)`.
- Foreign currency (SI/PI/JE): `base_amount = round(abs(raw_amount) * exchange_rate, 2)`.
- All posted documents carry `currency = source_currency` and `conversion_rate = exchange_rate`.

### 1) Income → Sales Invoice

One SI per row.

| ERP Field | Value |
|-----------|-------|
| `company` | `run.company` |
| `customer` | `row.resolved_party` |
| `posting_date` | `row.txn_date` |
| `due_date` | `row.txn_date` |
| `currency` | `row.source_currency` |
| `conversion_rate` | `row.exchange_rate` |
| `ignore_pricing_rule` | 1 |
| `taxes_and_charges` | null |
| `cashew_import_run` | `run.name` |
| `cashew_row_hash` | `row.source_hash` |
| `cashew_row_idx` | `row.row_idx` |

Item line (`item_code` omitted — not mandatory; `item_name` is the only required item field):

| ERP Field | Value |
|-----------|-------|
| `item_name` | `"{category} \| {month_key}"` (e.g., `"Freelance \| 2026-04"`) |
| `qty` | 1 |
| `rate` | `row.raw_amount` (in `source_currency`) |
| `income_account` | `row.resolved_account` |
| `cost_center` | company default cost center |

Submit after creation.

### 2) Expense > threshold → Purchase Invoice

One PI per row.

| ERP Field | Value |
|-----------|-------|
| `company` | `run.company` |
| `supplier` | `row.resolved_party` |
| `posting_date` | `row.txn_date` |
| `due_date` | `row.txn_date` |
| `currency` | `row.source_currency` |
| `conversion_rate` | `row.exchange_rate` |
| `ignore_pricing_rule` | 1 |
| `taxes_and_charges` | null |
| `cashew_import_run` | `run.name` |
| `cashew_row_hash` | `row.source_hash` |
| `cashew_row_idx` | `row.row_idx` |

Item line: same structure as SI (`item_name = "{category} | {month_key}"`), using `expense_account = row.resolved_account`.

Submit after creation.

### 3) Expense ≤ threshold → Journal Entry

One JE per row. No party required.

| JE Line | Account | Dr/Cr | Amount | Currency |
|---------|---------|-------|--------|----------|
| Line 1 | `resolved_account` (expense) | Debit | `raw_amount` | `source_currency` |
| Line 2 | `resolved_erp_account` (cash source) | Credit | `raw_amount` | `source_currency` |

| JE Field | Value |
|----------|-------|
| `posting_date` | `row.txn_date` |
| `multi_currency` | 1 if foreign currency, else 0 |
| `remark` | `"Cashew Import: {category} \| {title} \| {month_key} \| run:{run.name}"` |
| `cashew_import_run` | `run.name` |
| `cashew_row_hash` | `row.source_hash` |
| `cashew_row_idx` | `row.row_idx` |

Both lines carry `exchange_rate = row.exchange_rate`. Submit after creation.

### 4) Transfer Journal Entry (paired Balance Correction)

One JE per **pair**. When the async worker encounters the first leg of a pair it creates the JE; when the second leg is reached it finalizes and submits.

**Same-currency transfer:**

| JE Line | Account | Dr/Cr | Amount |
|---------|---------|-------|--------|
| Line 1 | dest `resolved_erp_account` | Debit | `dest_raw_amount` |
| Line 2 | source `resolved_erp_account` | Credit | `source_raw_amount` |

`exchange_rate = 1` on both lines. `posting_date` = source leg `txn_date`.

**Cross-currency transfer (e.g., USD → PKR):**

Implied rate (ensures JV balances in company currency):

```python
# Determine base amounts
if dest_currency == company_currency:
    dest_base     = dest_raw_amount
    implied_rate  = dest_base / source_raw_amount   # e.g. 9522.79 / 34.0
elif source_currency == company_currency:
    source_base   = source_raw_amount
    implied_rate  = source_raw_amount / dest_raw_amount
    dest_base     = dest_raw_amount  # dest is foreign — rare case
else:
    # Both foreign: convert dest to company currency via ERP rate
    dest_base    = round(dest_raw_amount * dest_erp_rate, 2)
    implied_rate = dest_base / source_raw_amount

source_base = round(source_raw_amount * implied_rate, 2)
imbalance   = abs(dest_base - source_base)

if imbalance > run.je_rounding_tolerance:
    # Mark both rows Error: TRANSFER_JV_IMBALANCE
else:
    # Post the JV
```

| JE Line | Account | debit/credit_in_account_currency | exchange_rate | base |
|---------|---------|----------------------------------|---------------|------|
| Line 1 (Debit) | dest `resolved_erp_account` | `dest_raw_amount` | 1 or `dest_erp_rate` | `dest_base` |
| Line 2 (Credit) | source `resolved_erp_account` | `source_raw_amount` | `implied_rate` | `source_base` |

| JE Field | Value |
|----------|-------|
| `posting_date` | source leg `txn_date` |
| `multi_currency` | 1 |
| `remark` | `"Cashew Transfer: {source} → {dest} \| {source_raw_amount} {src_cur} → {dest_raw_amount} {dst_cur} \| run:{run.name}"` |
| `cashew_import_run` | `run.name` |
| `cashew_row_hash` | source leg `source_hash` |
| `cashew_row_idx` | source leg `row_idx` |

Both row records store the same `posted_doctype` and `posted_docname`. Submit after finalization.

### 5) External Transfer JE (one-sided Balance Correction)

Used when only one leg is present in the file (the partner account is external, e.g., Meezan Bank).

Determined by row's `income_flag`:

| income_flag | Meaning | JE Debit | JE Credit |
|-------------|---------|----------|-----------|
| `true` (money arrived) | External account → my account | `resolved_erp_account` (my account) | `resolved_external_account` |
| `false` (money left) | My account → external account | `resolved_external_account` | `resolved_erp_account` (my account) |

Single-currency (typically PKR-to-PKR): `exchange_rate = 1`.

| JE Field | Value |
|----------|-------|
| `posting_date` | `row.txn_date` |
| `remark` | `"Cashew External Transfer: {transfer_source} → {transfer_dest} \| {raw_amount} {currency} \| run:{run.name}"` |
| `cashew_import_run` | `run.name` |
| `cashew_row_hash` | `row.source_hash` |
| `cashew_row_idx` | `row.row_idx` |

Submit after creation.

### 6) Adjustment JE (solo Balance Correction / Balance Transfer)

Single-sided JE for "Updated Total Balance", no-note, and any other non-paired Balance Correction or Balance Transfer rows.

`income_flag` determines direction:

| income_flag | Dr/Cr on `resolved_erp_account` | Dr/Cr on `balance_adjustment_account` |
|-------------|----------------------------------|---------------------------------------|
| `true` | Debit | Credit |
| `false` | Credit | Debit |

**Foreign-currency Adjustment rows** (e.g., `NSave +46.21 USD`):
- Follow the same exchange rate rules as SI/PI/JE foreign-currency rows.
- ERP rate pre-fills `exchange_rate` as a suggestion; accountant confirms in preview.
- Null `exchange_rate` at queue time → `EXCHANGE_RATE_MISSING`.
- `multi_currency = 1` on the JE; both lines carry `exchange_rate`.

| JE Field | Value |
|----------|-------|
| `posting_date` | `row.txn_date` |
| `remark` | `"Cashew Adjustment: {raw_amount} {currency} \| {note or 'no note'} \| run:{run.name} — Review Recommended"` |
| `cashew_import_run` | `run.name` |
| `cashew_row_hash` | `row.source_hash` |
| `cashew_row_idx` | `row.row_idx` |

Submit after creation. Row `posted_docname` stored. Diagnostics marks these rows with `review_recommended = true`.

### 7) Cash Settlement (auto_settle_cash)

Default: `auto_settle_cash = true` — Payment Entry created automatically for every SI and PI.
Cashew records actual cash events; there is no pending payment at import time.

If `auto_settle_cash = true` (default):
- After SI submit: Payment Entry (Receive), `payment_date = txn_date`, amount = SI grand_total, mode_of_payment = `run.default_mode_of_payment`. Link PE to SI.
- After PI submit: Payment Entry (Pay), same logic. Link PE to PI.

---

## C006 Idempotency Guard

**Primary check:** Query `Cashew Import Row` across all runs for `(source_hash, run.company)` where `posted_docname is not null`.

**Secondary check:** Query `cashew_row_hash` custom field on existing SI/PI/JE documents.

**On duplicate found:**
- Set `is_duplicate = 1`, `validation_status = "Skipped"`.
- Copy existing `posted_doctype` and `posted_docname` onto row.
- Increment `run.rows_skipped`. Do not raise error; continue.

**Transfer pairs:** Idempotency checked on source leg hash. Duplicate source leg → both legs skipped.

---

## C007 Async Worker + Progress Polling

- Queue: `frappe.enqueue("cashew_integration.importer.process_run", run_name=run.name, queue="long")`.
- Status path: `Draft → Queued → Processing → Completed` or `→ Failed`.
- Progress update every 20 rows (configurable via `cashew_progress_interval` site config key).
- On unhandled exception: `run.status = "Failed"`, `run.finished_on = now()`, log to `frappe.log_error`.
- **Retry:** A failed run can be re-queued by setting `status = "Queued"` and enqueuing again. Idempotency guard skips all already-posted rows safely.

---

## C008 Diagnostics CSV

Generated at run completion. Attached to `run.diagnostics_file`.

| Column | Source |
|--------|--------|
| `row_idx` | row |
| `txn_date` | row |
| `raw_account` | row |
| `amount` | row.raw_amount |
| `currency` | row.source_currency |
| `base_amount` | row |
| `exchange_rate` | row |
| `category` | row |
| `sub_category` | row |
| `title` | from parse |
| `txn_type` | row (Income / Expense / Transfer / External Transfer / Adjustment) |
| `resolved_route` | row |
| `resolved_account` | row |
| `resolved_erp_account` | row |
| `resolved_external_account` | row |
| `resolved_party` | row |
| `party_source` | row (Preview Override / Run Default) |
| `transfer_pair_row_idx` | row |
| `validation_status` | row (Valid / Error / Skipped) |
| `error_code` | row |
| `error_message` | row |
| `posted_doctype` | row |
| `posted_docname` | row |
| `is_duplicate` | row |
| `review_recommended` | 1 for Adjustment JE rows |

---

## C009 Install-Time Setup

Executed in `after_install` hook. All operations are idempotent (check-before-create).

### 1. Cashew Settings — create empty singleton

```python
if not frappe.db.exists("Cashew Settings", "Cashew Settings"):
    frappe.get_doc({"doctype": "Cashew Settings"}).insert(ignore_permissions=True)
```

### 2. Custom Fields

Installed on `Sales Invoice`, `Purchase Invoice`, and `Journal Entry`:

| Fieldname | Fieldtype | Label | Properties |
|-----------|-----------|-------|-----------|
| `cashew_import_run` | Link (Cashew Import Run) | Cashew Import Run | read-only, indexed |
| `cashew_row_hash` | Data | Cashew Row Hash | read-only, indexed |
| `cashew_row_idx` | Int | Cashew Row Index | read-only |

---

## Required Defaults Matrix

| Default | Source | Required For | Missing Behavior |
|---------|--------|-------------|-----------------|
| Company default cost center | ERPNext Company | SI, PI | Block queue: `RUN_CONFIG_MISSING` |
| Cashew Account Mapping (all `raw_account` values in file) | `Cashew Settings` child table | All routes | Block per row: `CASHEW_ACCOUNT_NOT_MAPPED` |
| Cashew Account Mapping (all external accounts in transfer notes) | `Cashew Settings` child table | External Transfer JE | Block per row: `EXTERNAL_ACCOUNT_NOT_MAPPED` |
| Category Mapping (all categories in file, non-Transfer non-Adjustment) | `Cashew Settings` child table | SI, PI, JE routes | Block per row at queue: `MAPPING_NOT_FOUND` |
| `run.default_customer` OR per-row party override | Run field | SI route | Block per row at queue: `PARTY_UNRESOLVED` |
| `run.default_supplier` OR per-row party override | Run field | PI route | Block per row at queue: `PARTY_UNRESOLVED` |
| `run.balance_adjustment_account` | Run field | Adjustment JE (when file contains Adjustment rows) | Block queue: `RUN_CONFIG_MISSING` |

---

## Permissions

| DocType | Accountant | System Manager |
|---------|------------|----------------|
| Cashew Settings | Read | All |
| Cashew Import Run | Read, Write, Create | All |
| Cashew Import Row (child) | Read (via parent) | Read |

Accountant cannot delete a `Cashew Import Run` once `status != Draft` (enforced in `before_delete`).

---

## Acceptance Criteria (v3)

1. Fresh Cashew export imports without manual edits — including multi-line notes, empty titles, emojis in titles, floating-point amounts, and mixed currencies.
2. All four account types (Petty Cash, Saving, NSave, Investment) and external accounts (Meezan Bank) are handled via `Cashew Account Mapping` — no code changes needed to add accounts.
3. Paired internal transfers post as a single Transfer JV; cross-currency pairs use implied rate so the JV balances by construction.
4. External-account orphan transfers (Meezan Bank → Saving, Saving → Meezan Bank) post as single-leg External Transfer JEs.
5. Solo Balance Correction / Balance Transfer rows (Updated Total Balance, no-note adjustments) always post as Adjustment JEs against `run.balance_adjustment_account`; missing this field when adjustment rows are present blocks the queue with a clear error.
6. SI/PI rows post using `run.default_customer` / `run.default_supplier` when no per-row party override is set; no party mapping rules required.
7. SI and PI submit with all required ERPNext fields; no tax lines applied.
8. Every SI and PI gets a linked Payment Entry by default (`auto_settle_cash = true`); AR/AP aging shows zero open balance on imported invoices.
9. Re-running the same file does not create duplicates; duplicates appear in diagnostics with original doc reference.
10. PKR and USD rows import with correct exchange-rate handling; ERP rate is a suggestion only — accountant confirms actual rate in preview.
11. All mapping config is maintained in `Cashew Settings` (one place); no company field on config rows; `company` exists only on the run.
12. A failed run re-queues safely; idempotency skips already-posted rows.
13. Diagnostics CSV covers every row: route, outcome, error code, review flag.

---

## Out of Scope (f001)

- API sync transport (f002)
- Heuristic voucher consolidation
- Advanced FX: revaluation entries, realized/unrealized gain-loss automation
- Rounding account auto-configuration (tolerance breach = error; accountant resolves manually)
