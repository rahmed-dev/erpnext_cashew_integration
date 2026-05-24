# c009 — dashboard-summary-endpoint

> **Type:** api (whitelisted method)
> **Depends on:** none (server-only; ships ahead of c007)
> **Arch refs:** D5 rule 4 (aggregates via purpose-built endpoint), D9 (GL-
> derived NOT run-aggregate), D5 rule 3 (`has_permission` at entry)
> **Consumer:** c007 finance-dashboard-page (sole caller)

---

## Overview

One whitelisted method, `cashew_integration.api.dashboard_summary`, that
returns the headline numbers for the SPA landing dashboard for a given
period + company. Pulled from GL Entry + Account (NOT from
`Cashew Import Run` aggregates per D9).

The function is read-only, side-effect-free, idempotent. Cached by the
frontend's `createResource` for the (period_start, period_end, company)
tuple; server does no caching v1.

---

## Method signature

```python
@frappe.whitelist()
def dashboard_summary(
    period_start: str | None = None,
    period_end: str | None = None,
    company: str | None = None,
) -> dict:
```

**Args:**
- `period_start`, `period_end`: ISO date strings (`YYYY-MM-DD`). If either is
  missing, raise `frappe.ValidationError("period_start and period_end required")`.
- `company`: Company name. If missing, default to
  `frappe.defaults.get_user_default("Company")` and raise
  `ValidationError("company required")` if still empty.

**Permission gate (D5.3) at the top of the function:**

```python
frappe.has_permission("GL Entry", "read", throw=True)
frappe.has_permission("Account", "read", throw=True)
frappe.has_permission("Company", "read", doc=company, throw=True)
```

`throw=True` raises `frappe.PermissionError` on deny — Frappe maps that to
a 403 response which the SPA error interceptor (c004) toasts.

---

## Response shape (binding)

```python
{
  "period": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
  "company": "Acme Pvt Ltd",
  "currency": "PKR",                # from Company.default_currency
  "income_total": 152400.00,        # positive number
  "expense_total": 88350.50,        # positive number (NOT negative)
  "income_by_category": [
    { "category": "Salary", "amount": 100000.00 },
    # ordered descending by amount; up to 5; sixth+ rolled into "(Other)"
  ],
  "expense_by_category": [
    { "category": "Rent", "amount": 35000.00 },
    # same shape; up to 5
  ],
  "balance_tiles": {
    "cash_bank":      { "amount": 425000.00, "prior_amount": 380000.00 | None },
    "receivable":     { "amount":  85000.00, "prior_amount":  95000.00 | None },
    "payable":        { "amount":  42000.00, "prior_amount":  38000.00 | None },
    "net_for_period": { "amount": 64049.50 }
  },
  "recent_runs": [
    {
      "name": "CASHEW-IMPORT-2026-000017",
      "status": "Completed",
      "period_start": "2026-04-01",
      "period_end": "2026-04-30",
      "rows_total": 126,
      "rows_valid": 124,
      "rows_failed": 2,
      "rows_posted": 124,
      "rows_skipped": 0,
      "modified": "2026-05-02T09:14:22",
    },
    # up to 5
  ],
}
```

All amounts: positive floats, rounded to 2 decimal places via `round(x, 2)`
before serialization (Decimal/float drift handled here once so the SPA
formats verbatim).

---

## Implementation

Inside `cashew_integration/api.py`, append a single new function:

```python
@frappe.whitelist()
def dashboard_summary(
    period_start: str | None = None,
    period_end: str | None = None,
    company: str | None = None,
) -> dict:
    """Finance overview for the SPA landing dashboard (D9). GL-derived.

    Args:
        period_start, period_end: ISO date strings; both required.
        company: Company name; defaults to user's default Company.

    Returns: dict shape per c009-spec.md.
    """
    if not period_start or not period_end:
        frappe.throw(_("period_start and period_end are required"))
    if not company:
        company = frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("company is required"))

    frappe.has_permission("GL Entry", "read", throw=True)
    frappe.has_permission("Account", "read", throw=True)
    frappe.has_permission("Company", "read", doc=company, throw=True)

    currency = frappe.db.get_value("Company", company, "default_currency") or "PKR"

    income_total, expense_total, income_cats, expense_cats = _period_pnl(
        company, period_start, period_end
    )

    balance_tiles = _balance_tiles(company, period_start, period_end,
                                   income_total - expense_total)

    recent_runs = _recent_runs(company)

    return {
        "period": {"start": period_start, "end": period_end},
        "company": company,
        "currency": currency,
        "income_total": _r(income_total),
        "expense_total": _r(expense_total),
        "income_by_category": income_cats,
        "expense_by_category": expense_cats,
        "balance_tiles": balance_tiles,
        "recent_runs": recent_runs,
    }


def _r(x: float | None) -> float:
    return round(float(x or 0.0), 2)
```

### `_period_pnl(company, start, end)` — income / expense totals + top categories

```python
def _period_pnl(company, start, end):
    """P&L for [start, end] using GL Entry + Account.root_type.

    Income: credit-debit sum across accounts where root_type='Income'
    Expense: debit-credit sum across accounts where root_type='Expense'

    Category attribution: GL Entry rows tied to Cashew Import Row may carry
    the originating cashew_category (joined via voucher_type/voucher_no -> 
    posted_doctype/posted_docname on Cashew Import Row). For rows not tied
    to a Cashew Import Row, attribute to "(Uncategorized)".
    """
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")

    pnl_rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.account, acc.root_type, gl.debit, gl.credit,
            gl.voucher_type, gl.voucher_no,
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
            & (acc.root_type.isin(["Income", "Expense"]))
        )
    ).run(as_dict=True)

    income_total = 0.0
    expense_total = 0.0
    income_by_cat: dict[str, float] = {}
    expense_by_cat: dict[str, float] = {}

    cat_lookup = _build_category_lookup(pnl_rows)

    for r in pnl_rows:
        cat = cat_lookup.get((r.voucher_type, r.voucher_no), "(Uncategorized)")
        if r.root_type == "Income":
            amt = (r.credit or 0.0) - (r.debit or 0.0)
            if amt <= 0:
                continue
            income_total += amt
            income_by_cat[cat] = income_by_cat.get(cat, 0.0) + amt
        else:  # Expense
            amt = (r.debit or 0.0) - (r.credit or 0.0)
            if amt <= 0:
                continue
            expense_total += amt
            expense_by_cat[cat] = expense_by_cat.get(cat, 0.0) + amt

    return (
        income_total,
        expense_total,
        _top_n_with_other(income_by_cat, 5),
        _top_n_with_other(expense_by_cat, 5),
    )


def _build_category_lookup(pnl_rows):
    """Map (voucher_type, voucher_no) -> cashew_category for rows that came
    from a Cashew Import Row posting. Single batched query."""
    voucher_keys = {(r.voucher_type, r.voucher_no) for r in pnl_rows
                    if r.voucher_type and r.voucher_no}
    if not voucher_keys:
        return {}

    row = frappe.qb.DocType("Cashew Import Row")
    mapping = frappe.qb.DocType("Cashew Category Mapping")

    rows = (
        frappe.qb.from_(row)
        .left_join(mapping).on(row.cashew_category == mapping.cashew_category)
        .select(
            row.posted_doctype, row.posted_docname,
            row.cashew_category,
        )
        .where(
            (row.posted_doctype.isin([k[0] for k in voucher_keys]))
            & (row.posted_docname.isin([k[1] for k in voucher_keys]))
            & (row.cashew_category.notnull())
        )
    ).run(as_dict=True)

    return {
        (r.posted_doctype, r.posted_docname): r.cashew_category or "(Uncategorized)"
        for r in rows
    }


def _top_n_with_other(by_cat: dict, n: int) -> list[dict]:
    items = sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
    head = items[:n]
    tail = items[n:]
    out = [{"category": c, "amount": _r(a)} for c, a in head]
    if tail:
        other_amt = sum(a for _, a in tail)
        out.append({"category": "(Other)", "amount": _r(other_amt)})
    return out
```

### `_balance_tiles(company, start, end, net_for_period)`

```python
def _balance_tiles(company, period_start, period_end, net_for_period):
    """Period-end balances for cash/bank, receivable, payable. Plus
    prior-period balance for delta display (None if no prior period).
    """
    prior_end = _date_minus_1(period_start)            # day before start
    prior_start = _shift_back_same_span(period_start, period_end)

    def _balance(account_filters: dict, as_of: str) -> float:
        """Sum GL debit - credit (or credit - debit per root_type) up to as_of."""
        gl = frappe.qb.DocType("GL Entry")
        acc = frappe.qb.DocType("Account")
        rows = (
            frappe.qb.from_(gl)
            .inner_join(acc).on(gl.account == acc.name)
            .select(acc.root_type, gl.debit, gl.credit)
            .where(
                (gl.company == company)
                & (gl.posting_date <= as_of)
                & (gl.is_cancelled == 0)
                & _account_qb_filter(acc, account_filters)
            )
        ).run(as_dict=True)
        total = 0.0
        for r in rows:
            if r.root_type in ("Asset",):
                total += (r.debit or 0.0) - (r.credit or 0.0)
            else:  # Liability, Equity
                total += (r.credit or 0.0) - (r.debit or 0.0)
        return total

    cash_bank_amount       = _balance({"account_type": ["in", ["Bank", "Cash"]]}, period_end)
    cash_bank_prior        = _balance({"account_type": ["in", ["Bank", "Cash"]]}, prior_end) if prior_end else None
    receivable_amount      = _balance({"account_type": "Receivable"},             period_end)
    receivable_prior       = _balance({"account_type": "Receivable"},             prior_end) if prior_end else None
    payable_amount         = _balance({"account_type": "Payable"},                period_end)
    payable_prior          = _balance({"account_type": "Payable"},                prior_end) if prior_end else None

    return {
        "cash_bank":      {"amount": _r(cash_bank_amount), "prior_amount": _r(cash_bank_prior) if cash_bank_prior is not None else None},
        "receivable":     {"amount": _r(receivable_amount), "prior_amount": _r(receivable_prior) if receivable_prior is not None else None},
        "payable":        {"amount": _r(payable_amount),    "prior_amount": _r(payable_prior)    if payable_prior is not None else None},
        "net_for_period": {"amount": _r(net_for_period)},
    }


def _date_minus_1(d: str) -> str:
    from datetime import datetime, timedelta
    return (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def _shift_back_same_span(start: str, end: str) -> str:
    """Returns a date equal to start − (end - start) for prior-period framing.
    Used only as a hint; we surface the prior-period delta as Balance−Prior."""
    from datetime import datetime, timedelta
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    return (s - (e - s)).strftime("%Y-%m-%d")


def _account_qb_filter(acc_qb, filters: dict):
    """Translate a small filter dict into a frappe.qb predicate chain."""
    pred = None
    for k, v in filters.items():
        if isinstance(v, list) and len(v) == 2 and v[0] == "in":
            p = getattr(acc_qb, k).isin(v[1])
        else:
            p = getattr(acc_qb, k) == v
        pred = p if pred is None else (pred & p)
    return pred
```

### `_recent_runs(company)`

```python
def _recent_runs(company: str) -> list[dict]:
    """Top 5 most-recent Cashew Import Run for this company.
    Read via frappe.get_all (NOT ignoring permissions) — so the user only
    sees runs they can see. Drives the dashboard's Recent Imports strip.
    """
    rows = frappe.get_all(
        "Cashew Import Run",
        filters={"company": company},
        fields=[
            "name", "status", "company",
            "period_start", "period_end",
            "rows_total", "rows_valid", "rows_failed", "rows_posted", "rows_skipped",
            "modified",
        ],
        order_by="modified desc",
        limit=5,
        ignore_permissions=False,
    )
    return rows
```

---

## Permissions: D5 rule 4 in detail

The function explicitly calls `has_permission` for GL Entry, Account, and
Company (the company being queried). Internally `frappe.get_all` honors
DocPerms + User Permissions by default — we keep `ignore_permissions=False`
on `_recent_runs` so a user without read access to a particular run won't
see it in the strip.

For raw `frappe.qb` reads over GL Entry, frappe-qb does NOT auto-filter by
User Permissions. The single `has_permission("GL Entry", "read", throw=True)`
at entry checks the doctype-level perm. User-Permission rows are filtered
post-hoc by company filter (already in the WHERE clause). If a future
requirement needs row-level perm filtering on GL aggregations, switch to
`frappe.get_all` with `ignore_permissions=False` (slower but exact). v1
ships the company-filtered raw qb path.

---

## Files touched

```
cashew_integration/cashew_integration/api.py     # APPEND dashboard_summary + helpers
```

Single file edit. No new modules.

---

## Error surface

- Missing `period_start`/`period_end`/`company` → `frappe.ValidationError`
  (HTTP 417 by Frappe convention).
- User lacks `GL Entry:read` or `Account:read` or `Company:read` on the
  requested company → `frappe.PermissionError` (HTTP 403).
- Date parse failure → `ValueError` rises to a 500; c004's interceptor
  toasts "Server error. Please retry." (acceptable v1; tighten if real).

---

## Performance notes

For a single company over a month-long period, the GL Entry table for the
P&L window is small (hundreds to low thousands of rows on a typical
Cashew-import bookkeeping setup). All queries are indexed
(`gl.posting_date`, `gl.company`, `gl.account` are all indexed by ERPNext
core). No `JOIN GL Entry x GL Entry`; everything is single-pass with one
inner join to Account.

The `_build_category_lookup` issues one extra query batched on the
voucher_no set from the period — typically <2000 rows; acceptable.

Server-side caching deferred. If a single call exceeds ~1s in prod,
introduce `frappe.cache().get_value/set_value` with a 60s TTL keyed on
`(company, period_start, period_end)`.

---

## Acceptance

- [ ] `frappe.call('cashew_integration.api.dashboard_summary', { period_start: '2026-05-01', period_end: '2026-05-24', company: 'Acme Pvt Ltd' })` returns the documented shape with `income_total`, `expense_total`, `currency`, four `balance_tiles`, ordered `income_by_category` / `expense_by_category` (descending, up to 6 with `(Other)`), and up to 5 `recent_runs`.
- [ ] Numbers match a manual GL Entry SQL read across the same period.
- [ ] Currency reflects `Company.default_currency` (not hardcoded).
- [ ] Categories with zero amount don't appear in the lists.
- [ ] `(Uncategorized)` shows for GL rows with no Cashew Import Row backlink.
- [ ] Top-5 with `(Other)` rollup works when there are more than 5 categories.
- [ ] Missing `period_start` / `period_end` raises `ValidationError`.
- [ ] User lacking `GL Entry:read` gets `PermissionError`.
- [ ] User without read access to a specific run doesn't see it in
      `recent_runs` (verify with a 2-user test: User Permission on Company
      hides runs in the other Company).
- [ ] Endpoint is whitelisted (`@frappe.whitelist()`); browser can call.
- [ ] Function is side-effect-free (no `db.set_value`, no `doc.save`, no
      `publish_realtime` — purely read).

---

## TD calls inside arch envelope (not surfacing)

- **GL Entry as the source.** D9 prescribes GL-derived (not run-aggregate).
  Picked `posting_date` window over `creation` because a re-posted run
  may have a posting date in the past — the dashboard reflects "what
  happened in this period" not "what got posted in this window".
- **`is_cancelled=0` filter.** Frappe convention; cancelled GL Entries
  exist as audit trail but don't represent live financial state.
- **Cash & Bank tile groups account_type `Bank` + `Cash`.** Matches the
  finance-dashboard brief headline + how ERPNext's chart-of-accounts
  organizes liquid asset accounts.
- **Receivable / Payable balance via root_type math.** Receivable is an
  Asset (debit-balance); Payable is a Liability (credit-balance). Single
  helper does the sign math by root_type.
- **`prior_amount` = balance at (period_start − 1 day).** Simple and
  cheap. Future iteration could compare period-over-period (last
  month's same range); v1 deferred.
- **Top-N + `(Other)` rollup.** Brief asks for up to 5 categories per
  side. `(Other)` keeps the totals reconcilable when there are >5.
- **`frappe.qb` over GL Entry, not `frappe.get_all`.** qb is faster for
  multi-million-row GL tables. Company is in the WHERE so user-permission
  drift is bounded; doctype-level perm check at top guards the rest.
- **Currency from Company.default_currency**, not boot. The dashboard is
  per-company; boot's currency is per-user default, which can mismatch
  when the user switches CompanySelector.

---

## Open items (handed off)

- **No category rollup hierarchy.** Cashew categories are flat strings;
  no parent/child grouping. If categories grow, consider a category-
  group field. Out of scope.
- **No drill-through.** Tile click → ledger report deferred.
- **No multi-company aggregate.** One-company-at-a-time per the
  CompanySelector. Multi-company consolidated view = future feature.
- **No caching.** Re-add via `frappe.cache().hset()` if dashboard calls
  fire frequently and GL Entry grows large.
- **Realtime invalidation strategy** (c008 territory): SPA debounces
  re-fetches; server has no realtime invalidation logic. If realtime
  becomes a hotspot, switch the SPA to subscribe to a synthetic
  `dashboard.refresh` event published by the post worker, and pull
  fresh data.
