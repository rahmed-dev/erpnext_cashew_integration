# Spec: c001 — schema-loan-and-category-type

Story: [c001-story.md](./c001-story.md)
Architecture: f006 Decisions 1, 4, 5; system-arch decisions-log "Cashew Account Mapping", "Configuration Structure", "Posting Targets by Transaction Type".
TD decision (resolves Decision 1 open D1.a): **two distinct `txn_type` values** — `Loan Receivable` and `Loan Payable` — over a single `Loan` value with sub-route. Mirrors `resolved_route` shape, matches existing `Transfer` / `External Transfer` split pattern, gives Vue Row Explorer a clean filter predicate.

## Overview

Schema deltas only — no business logic. Three doctypes touched, one controller added, one shared validation helper added. Foundation for the rest of f006:
- **c002** parser routing reads `category_type`
- **c003** mapping engine simplified (drop rule-based party fallback, validate against `category_type`)
- **c004** loan posting handler reads new `txn_type` values
- **c006** Vue Row Explorer filters on `category_type` + new `txn_type`s
- **c008** loan-accounts existence guard layers on top of the save-time class check

## Component Detail

```yaml
id: c001
name: schema-loan-and-category-type
type: doctype
depends_on: []
```

### Field deltas

#### Cashew Category Mapping (`istable: 1`)

| field | type | options / settings | reqd | notes |
|---|---|---|---|---|
| `category_type` | Select | `Income\nExpense\nLoan Out\nLoan In` | 1 | **NEW.** default `Income` (so existing rows pass validate on first re-save without an explicit backfill — c009 was dropped). `in_list_view: 1`. Position: after `cashew_sub_category`, before `default_account`. |
| `default_account` | Link → Account | static `link_filters` (baseline) + dynamic per `category_type` (client JS) | 1 (unchanged) | **MODIFIED.** Filter tightens with `category_type`. |

`default_account.link_filters` matrix (applied dynamically by client JS on row's `category_type` change; server validate is the safety net):

| `category_type` | filter |
|---|---|
| Income | `is_group=0`, `root_type=Income` |
| Expense | `is_group=0`, `root_type=Expense` |
| Loan Out | `is_group=0`, `root_type=Asset`, `account_type=Receivable` |
| Loan In | `is_group=0`, `root_type=Liability`, `account_type=Payable` |

#### Cashew Import Row

| field | change |
|---|---|
| `txn_type` | options extended: `Income\nExpense\nTransfer\nExternal Transfer\nAdjustment\nLoan Receivable\nLoan Payable` (added two) |
| `resolved_route` | options extended: `\nJournal Entry\nTransfer JV\nExternal Transfer JE\nAdjustment JE\nLoan Receivable JE\nLoan Payable JE` (added two) |

#### Cashew Import Run

| field | change |
|---|---|
| `default_customer` | `hidden: 1` (column kept nullable for f004 revert backward compat) |
| `default_supplier` | `hidden: 1` (column kept nullable for f004 revert backward compat) |

### Endpoints / controllers

**New file:** `cashew_integration/cashew_integration/doctype/cashew_category_mapping/cashew_category_mapping.py`

```python
import frappe
from frappe.model.document import Document
from cashew_integration.importer.validation import check_category_account_class


class CashewCategoryMapping(Document):
    def validate(self):
        msg = check_category_account_class(self.category_type, self.default_account)
        if msg:
            frappe.throw(msg)
```

**New helper:** `cashew_integration/importer/validation.py::check_category_account_class(category_type: str, account_name: str | None) -> str | None`

- Returns `None` if class matches; otherwise a friendly message.
- Predicate (single source of truth, used by save-time controller AND validate-time loop):

  | category_type | required `Account.root_type` | required `Account.account_type` |
  |---|---|---|
  | Income | `Income` | (any) |
  | Expense | `Expense` | (any) |
  | Loan Out | `Asset` | `Receivable` |
  | Loan In | `Liability` | `Payable` |

- Skip when `account_name` is falsy — required-field guard handles missing account elsewhere.
- Message shape: `Account '{account_name}' has root_type '{actual_root}' / account_type '{actual_type}', but category_type '{category_type}' requires root_type '{expected_root}' / account_type '{expected_type}'.`

**`validate_import` integration** (`cashew_integration/importer/validation.py`): per-row check loop, after Cashew Category Mapping is resolved for a row, calls `check_category_account_class(mapping.category_type, mapping.default_account)`. On mismatch:
- `validation_error_code = "CATEGORY_ACCOUNT_CLASS_MISMATCH"`
- `validation_error_message = "[Row {row_idx}] " + msg` (Decision 5 prefix)
- `validation_status = "Error"`

**Scope:** validate-time predicate runs only for rows whose category is in Cashew Category Mapping — i.e. Income / Expense / Loan rows. Transfer-family rows (see "Transfer-family scoping" below) bypass the predicate entirely.

### Data flow

```mermaid
flowchart TD
    A[Accountant edits Cashew Settings]
    A -->|saves Category Mapping row| B[CashewCategoryMapping.validate]
    B --> P[check_category_account_class<br/>category_type vs Account.root_type/account_type]
    P -->|mismatch| D[frappe.throw — friendly error]
    P -->|ok| E[saved]

    F[CSV imported] --> G[parser c002]
    G -->|Income/Expense/Loan rows<br/>read category_type from Mapping| H[Cashew Import Row<br/>txn_type / resolved_route<br/>per Decision 1 routing table]
    G -->|category in TRANSFER_CATEGORIES| TX[Transfer/External Transfer/<br/>Adjustment — bypass mapping]
    H --> I[validate_import]
    TX --> I
    I -->|Income/Expense/Loan rows only| P2[check_category_account_class<br/>same predicate, per row]
    P2 -->|mismatch| K[validation_status=Error<br/>code=CATEGORY_ACCOUNT_CLASS_MISMATCH<br/>msg='[Row N] Account X has...']
    P2 -->|ok| L[validation_status=Valid]
    I -->|Transfer-family rows| L
```

### Permissions

- **Cashew Category Mapping** — child of Cashew Settings singleton; permissions inherited from parent.
- **Cashew Import Row** — child of Cashew Import Run; permissions inherited.
- **Cashew Import Run** — `default_customer` / `default_supplier` hide is layout-only; permission rules unchanged.
- No new role. Accountant role (per system-arch Primary User) interacts with all three.

### Frappe hooks

None added to `hooks.py`. Standard doctype controller `validate` method is auto-wired by Frappe.

## Transfer-family scoping (important)

`category_type` is a property of **user-mapped categories only**. It does not apply to:

- **Transfer** (paired internal — both legs in the file, matched via `transfer_pair_row_idx`)
- **External Transfer** (one leg in the file, partner account outside via `resolved_external_account`)
- **Adjustment** ("Updated Total Balance" / unmatched note — hits `balance_adjustment_account`)

These three are detected by the parser based on `TRANSFER_CATEGORIES = {"Balance Correction", "Balance Transfer"}` and the `_classify_transfer_rows()` regex pass on `note`. They bypass Cashew Category Mapping entirely — no `category_type`, no account-class predicate. This matches current f001 behavior and stays unchanged in f006.

A Cashew row is therefore in **exactly one** of two disjoint regimes:
1. **Mapped category regime** — category exists in Cashew Category Mapping; `category_type` drives `txn_type` ∈ {Income, Expense, Loan Receivable, Loan Payable}; account-class predicate applies.
2. **Transfer-family regime** — category ∈ TRANSFER_CATEGORIES; classification pass sets `txn_type` ∈ {Transfer, External Transfer, Adjustment}; predicate skipped.

The two regimes never overlap. A user can't accidentally tag "Balance Correction" with `category_type = Loan Out` because that string isn't in Cashew Category Mapping — it's a magic CSV value.

## Notes / gotchas

- **`default_customer` / `default_supplier` are hide-only, never delete.** f004 revert paths read existing Cashew Import Run records by name; dropping these columns would break revert on historical runs. Hidden on form layout, columns kept nullable in DB. Decision 2 implication.
- **`requires_party` semantic.** Stays as-is for Income/Expense (existing meaning). Ignored for Loan rows — c003/c004 hardcode: Loan Out → Customer required, Loan In → Supplier required. Don't repurpose this flag.
- **No backfill component (c009 dropped 2026-05-03).** Default `Income` on the schema field is sufficient — existing Cashew Category Mapping rows load with `category_type=Income` and pass validate on read. They only re-trigger validate when the user edits and saves them; at that point the user picks the correct `category_type` themselves. No data-migration risk because existing Cashew Import Run / Import Row records are frozen (per f004 revert principle) and don't reference `category_type`.
- **Dynamic `link_filters` lives in client JS.** The doctype JSON keeps the static `is_group=0` baseline; the JS controller listens on row `category_type` change and re-applies the tighter filter. Server-side `validate` is the safety net (predicate runs regardless of how the link was picked, including programmatic writes).
- **Loan account existence** is c008's job. c001 only enforces class match on whatever account was picked.
- **`txn_type` / `resolved_route` are read-only on the row.** Parser sets them; user never picks. Just enum option additions on the JSON.
- **Idempotency unaffected.** `source_hash` is computed from CSV-row content (date, income, category, sub_category, amount, currency, account, note) — independent of `category_type` / `txn_type` / route.
- **No new dependencies, no hooks.py change, no scheduled jobs.**

## Files affected

| file | change |
|---|---|
| `cashew_integration/cashew_integration/doctype/cashew_category_mapping/cashew_category_mapping.json` | add `category_type` Select field; tighten static link_filters baseline if desired |
| `cashew_integration/cashew_integration/doctype/cashew_category_mapping/cashew_category_mapping.py` | new — `validate` method calling `check_category_account_class` |
| `cashew_integration/cashew_integration/doctype/cashew_category_mapping/cashew_category_mapping.js` | new — dynamic `link_filters` on `category_type` change |
| `cashew_integration/cashew_integration/doctype/cashew_import_row/cashew_import_row.json` | extend `txn_type` + `resolved_route` Select options |
| `cashew_integration/cashew_integration/doctype/cashew_import_run/cashew_import_run.json` | `hidden: 1` on `default_customer` + `default_supplier` |
| `cashew_integration/importer/validation.py` | add `check_category_account_class` helper; wire into per-row validate loop with new error code `CATEGORY_ACCOUNT_CLASS_MISMATCH` |

## Acceptance verification (Dev hand-off checklist)

- [ ] `bench --site work.local migrate` succeeds; new `category_type` column present on Cashew Category Mapping with default `Income`.
- [ ] Saving a Cashew Category Mapping row with `category_type=Expense` and an Income-rooted `default_account` raises ValidationError with the friendly message format.
- [ ] Same for `Loan Out` with a non-Receivable Asset account, `Loan In` with a non-Payable Liability account, etc.
- [ ] Existing import-run records still open, list, and revert without errors (default_customer/default_supplier hidden but readable).
- [ ] `validate_import` on a run whose Cashew Category Mapping was tampered post-save (account changed root_type) flags affected rows with `CATEGORY_ACCOUNT_CLASS_MISMATCH` and `[Row N]` prefix.
- [ ] Parser still classifies Balance Correction / Balance Transfer rows into Transfer / External Transfer / Adjustment without consulting `category_type` (regression check on existing test_parser test).

status: approved
