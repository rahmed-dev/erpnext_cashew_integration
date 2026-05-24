# c010 — api-permission-audit

> **Type:** refactor (audit + minimal fixes)
> **Depends on:** none (pre-flight for c005/c006/c012 SPA writes)
> **Arch refs:** D5 rule 3 (writes via `cashew_integration/api.py`
> whitelisted methods MUST call `frappe.has_permission(...)` at entry)
> **Scope:** every whitelisted method in `cashew_integration/api.py` +
> any other whitelisted writes added by f001 / f004 / f006 / f009.

---

## Overview

The SPA delegates every write to existing `cashew_integration/api.py`
whitelisted methods (D5 rule 3). Each method MUST gate on
`frappe.has_permission(doctype, ptype, doc=...)` at the top. This spec
walks the existing surface, confirms each entry's gate is present and
correct, and adds gates where missing.

The audit is **read-only investigation + tiny patches**; no behavior
change to the endpoints themselves. Largely a verification pass with
zero diff in the success case.

---

## Method-by-method audit table

Each row below verified against current code. ✓ = gate present + correct.
✗ = missing / weak; needs the noted fix.

| Method | File:line | Doctype gated | `ptype` | Verdict | Note |
|---|---|---|---|---|---|
| `parse_and_preview` | api.py:65 | Cashew Import Run | (default `write`) | ✓ | `frappe.has_permission("Cashew Import Run", doc=run, throw=True)` at L77. Mutates run + child rows; write perm correct. |
| `validate_import` | api.py:132 | Cashew Import Run | default `write` | ✓ | L140 gate. Writes row validation_status + run counters. |
| `queue_run` | api.py:270 | Cashew Import Run | default `write` | ✓ | L281 gate. Enqueues background job. |
| `revert_run` | api.py:344 | Cashew Import Run | default `write` | ✓ | L355 gate. Destructive; write is correct. |
| `cancel_run` | api.py:372 | Cashew Import Run | default `write` | ✓ | L380 gate. |
| `get_run_progress` | api.py:397 | Cashew Import Run | default `write` | **FIX** | Read-only endpoint; the default `write` is too strict. Change to `ptype="read"` so any user who can see the run can poll it (matches the polling-fallback use case from c008). |
| `setup_from_csv` | api.py:421 | Cashew Import Run | — | **FIX** | No gate; creates a new Cashew Import Run. Add `frappe.has_permission("Cashew Import Run", ptype="create", throw=True)` at entry. Also gate `Company` read on the supplied `company` arg. |
| `row_explorer_load` | api.py:497 | Cashew Import Run | `read` | ✓ | L504 explicit read gate. |
| `row_explorer_set_party` | api.py:532 | Cashew Import Run | `write` | ✓ | L543 explicit write gate. |
| `row_explorer_revalidate` | api.py:583 | Cashew Import Run | `write` | ✓ | L592 explicit write gate. |
| `dashboard_summary` (NEW from c009) | api.py | GL Entry / Account / Company | `read` | ✓ | c009 spec already prescribes the three has_permission throws. Audit confirms when c009 lands. |

**Outcome:** 2 fixes (`get_run_progress` perm-too-strict, `setup_from_csv`
missing gate). The rest already comply.

---

## Required patches

### Patch 1: `get_run_progress` → read perm

```python
# api.py around L397
@frappe.whitelist()
def get_run_progress(run_name: str) -> dict:
    run = frappe.get_doc("Cashew Import Run", run_name)
-   frappe.has_permission("Cashew Import Run", doc=run, throw=True)
+   frappe.has_permission("Cashew Import Run", ptype="read", doc=run, throw=True)
    return {
        "status": run.status,
        "rows_total": run.rows_total or 0,
        # ... rest unchanged
    }
```

### Patch 2: `setup_from_csv` → add gate

```python
# api.py around L421
@frappe.whitelist()
def setup_from_csv(file_url: str, company: str | None = None) -> dict:
+   frappe.has_permission("Cashew Import Run", ptype="create", throw=True)
+   if company:
+       frappe.has_permission("Company", ptype="read", doc=company, throw=True)
    # ... rest unchanged
```

---

## Doctype-level perm check (sanity pass)

Confirm the following DocPerm baselines exist for the role gate
("System Manager" OR "Accounts Manager") in:

- `Cashew Import Run` — read/create/write for the gated roles.
- `Cashew Import Row` — inherits via child-table parent (no explicit
  DocPerm needed; perms cascade from parent doctype on save/get_doc).
- `Cashew Settings` (Single) — read for both gated roles; write for
  System Manager only (Accounts Manager read-only). This drives
  c012's ReadOnlyBanner via `boot.can_write_settings`.
- `Cashew Category Mapping`, `Cashew Account Mapping` — Desk CRUD;
  not touched by SPA writes; no changes required.

If `Cashew Settings` DocPerm doesn't restrict Accounts Manager to
read-only, this is the place to fix it. Verify with:

```python
frappe.permissions.get_doc_permissions(
    frappe.get_doc("Cashew Settings", "Cashew Settings"),
    user="<accounts-manager-test-user>",
)
# expect: {'read': 1, 'write': 0, 'create': 0, 'delete': 0}
```

If write=1 for Accounts Manager, add a DocPerm row that allows read
only, OR adjust the existing rows.

---

## set_value writes from the SPA — c012 path

c012 saves Cashew Settings via `frappe.client.set_value`. Frappe's
`set_value` handler checks `frappe.has_permission(doctype, "write",
doc=...)` automatically. No api.py method to gate; the framework
covers it. The audit just confirms the Cashew Settings write
permission is correctly set per the previous section.

---

## Files touched

```
cashew_integration/cashew_integration/api.py     # EDIT — 2 small patches
```

If DocPerm baselines need adjustment for Cashew Settings:
```
cashew_integration/cashew_integration/doctype/cashew_settings/cashew_settings.json   # EDIT — permissions array
```

Otherwise: zero JSON edits.

---

## Acceptance

- [ ] `get_run_progress` now uses `ptype="read"`. A user with only
      read perm on a Cashew Import Run can call it.
- [ ] `setup_from_csv` raises `frappe.PermissionError` for a user
      without `Cashew Import Run` create perm.
- [ ] All other methods unchanged.
- [ ] `Cashew Settings` write restricted to System Manager;
      Accounts Manager gets `boot.can_write_settings === false` →
      c012 ReadOnlyBanner shows.
- [ ] No test regressions in `tests/`.

---

## TD calls inside arch envelope (not surfacing)

- **Don't refactor signatures.** Method args / response shapes
  unchanged; the SPA already binds to them.
- **`ptype="create"` for setup_from_csv** rather than `"write"`,
  because the call creates a fresh doc. Matches Frappe convention.
- **No new tests required v1.** Existing tests in `tests/` cover
  successful paths. Permission-denied paths would be a nice add but
  out of scope for the audit pass.

---

## Open items (handed off)

- **Add a permission-denied test per method.** Would catch future
  regressions of this exact issue. Out of f010 scope; track as a
  follow-up test ticket.
- **`Cashew Settings.validate` field write perm** — c013 adds
  `accent_color`, `accent_color_custom`, and the validator hook.
  The validator runs server-side on `set_value`; no perm change
  needed.
