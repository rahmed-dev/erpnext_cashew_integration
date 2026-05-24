# c011 — realtime-emission-audit

> **Type:** refactor (audit + targeted emissions)
> **Depends on:** none (pre-flight / parallel to c008)
> **Arch refs:** D8 (Socket.IO doc_update emission), c008 contract
> (per-run subscription, normalized `{ doc?, rows? }` event shape)

---

## Overview

Audit every Cashew worker code path that mutates `Cashew Import Run` or
`Cashew Import Row` state. Confirm each emits a realtime event that
c008's `subscribeDoc('Cashew Import Run', name, ...)` consumer can pick
up. Add emissions where missing. Minimal changes; behavior preserved.

Two doctype concerns:

1. **Cashew Import Run.status / counters** — Run-level state changes
   that drive section swap + RunHeader counters in c006.
2. **Cashew Import Row fields** — Per-row mutations
   (`validation_status`, `posted_doctype`, `posted_docname`,
   `revert_status`, `revert_error`) that drive live row patches in
   c006's RowsWorkbench.

---

## Audit table — current state vs target

### Cashew Import Run (status / counters)

| Code path | File:line | Current write | Auto-emit? | Verdict |
|---|---|---|---|---|
| `_process` start → Processing | worker.py:82 | `run.db_set("status", "Processing", notify=True)` | ✓ (notify=True) | ✓ |
| `_process` start → started_on | worker.py:83 | `run.db_set("started_on", now(), notify=True)` | ✓ | ✓ |
| `_process` end → finished_on | worker.py:109 | `run.db_set("finished_on", now(), notify=True)` | ✓ | ✓ |
| `_process` end → diagnostics_file | worker.py:197 | `run.db_set("diagnostics_file", diag_file, notify=True)` | ✓ | ✓ |
| `_process` end → status (Completed/Failed) | worker.py:203 | `run.db_set("status", final_status, notify=True)` | ✓ | ✓ |
| `_process` end → finished_on (2nd) | worker.py:204 | `run.db_set("finished_on", now(), notify=True)` | ✓ | ✓ |
| `_process` exception → Failed / finished | worker.py:66 / 67 | both `notify=True` | ✓ | ✓ |
| `_revert` end → final status | worker.py:236 / 237 / 303 / 304 | all `notify=True` | ✓ | ✓ |
| api.py `_set_run_status` (queue/cancel/revert button paths) | api.py:~206, ~300 | `frappe.db.set_value("Cashew Import Run", ...)` **without** `update_modified=False` AND **without** explicit notify | **CHECK** | `frappe.db.set_value` defaults: emits via Frappe Realtime via the `notify` kwarg = False unless overridden. Verify exact Frappe v15/16 default; if no auto-emit, add explicit `frappe.publish_realtime('doc_update', {doctype:'Cashew Import Run', name:run_name}, doctype='Cashew Import Run', docname=run_name)`. **FIX in patch 1.** |

**Counters** (`rows_total`, `rows_valid`, `rows_failed`, `rows_posted`,
`rows_skipped`): these are incremented inside the worker via
`run.db_set(...)` with `notify=True` (verify each call site; the
existing notify=True pattern carries to counter writes). If any
counter write uses `frappe.db.set_value` without notify, convert.

### Cashew Import Row (per-row mutations)

| Code path | File:line | Current write | Auto-emit? | Verdict |
|---|---|---|---|---|
| Worker post-row write | worker.py:277, 287, 296, 307 | `frappe.db.set_value("Cashew Import Row", row["name"], {...})` | ✗ no notify | **FIX in patch 2** |
| `_write_row_result` after posting | worker.py:333 | same | ✗ | **FIX in patch 2** |
| api.py `row_explorer_set_party` row write | api.py | uses `set_value` (whitelisted method path) | ✗ | **FIX in patch 2** |
| api.py `row_explorer_revalidate` row write | api.py | re-runs validation, writes via `set_value` | ✗ | **FIX in patch 2** |
| validate_import inner loop writes | api.py | `set_value` per row | ✗ | **FIX in patch 2** |

`Cashew Import Row` is a child table; Frappe's child-doc realtime
isn't a thing the SPA can subscribe to cleanly (Frappe doesn't emit
per-child events). c008's contract is: subscribe to the **parent**
(`Cashew Import Run`); the worker emits a synthetic event carrying
changed-row data under `rows: [...]`.

---

## Required patches

### Patch 1: `Cashew Import Run` writes from api.py — explicit notify

Wrap the two `frappe.db.set_value("Cashew Import Run", ...)` call sites
in api.py (L206, L300) to use `run.db_set(..., notify=True)` or pass
`notify=True` explicitly. Cleaner: re-fetch the doc and call db_set:

```python
# api.py ~L206 (inside queue_run or cancel_run; verify exact context)
- frappe.db.set_value("Cashew Import Run", run.name, {"status": "Queued"})
+ run.db_set("status", "Queued", notify=True)
```

Repeat for L300. (Both currently work via the doc-update default; this
is belt-and-braces for v15→v16 portability.)

### Patch 2: Worker / api.py Cashew Import Row writes — synthetic parent emission

Add a small helper next to `_write_row_result`:

```python
# worker.py (or a new emit_helpers.py module)
def _emit_row_update(run_name: str, row_patch: dict) -> None:
    """Publish a synthetic parent-run doc_update carrying per-row patches.
    c008's consumer listens on the parent Cashew Import Run subscription
    and dispatches the `rows` array to per-row patchers."""
    frappe.publish_realtime(
        event="doc_update",
        message={
            "doctype": "Cashew Import Run",
            "name": run_name,
            "rows": [row_patch],
        },
        doctype="Cashew Import Run",
        docname=run_name,
    )
```

`row_patch` shape:
```python
{
  "row_idx": int,
  # plus any of: validation_status, validation_error_code,
  # validation_error_message, posted_doctype, posted_docname,
  # posted_gl_date, revert_status, revert_error, resolved_party,
  # resolved_party_type, resolved_account, resolved_external_account,
  # is_duplicate
}
```

Wire calls into the four worker locations + the three api.py write
methods. Sketch:

```python
# worker.py L277 (revert path) — after set_value:
  frappe.db.set_value("Cashew Import Row", row["name"], {
      "revert_status": "Reverted",
      "revert_error":  None,
      "posted_doctype": None,
      "posted_docname": None,
  })
+ _emit_row_update(run_name, {
+     "row_idx": row["row_idx"],
+     "revert_status": "Reverted",
+     "revert_error": None,
+     "posted_doctype": None,
+     "posted_docname": None,
+ })
  reverted += 1
```

Repeat at L287, L296, L307, and after `_write_row_result` at L333.

For `api.py row_explorer_set_party`: emit one event per row in the
batch (or one event with `rows: [...]` carrying all). Latter is
slightly more efficient over the wire:

```python
# api.py inside row_explorer_set_party after the set_value loop
+ patches = [{
+     "row_idx": idx,
+     "resolved_party_type": party_type,
+     "resolved_party": party,
+ } for idx in row_indices]
+ frappe.publish_realtime(
+     event="doc_update",
+     message={"doctype": "Cashew Import Run", "name": run_name, "rows": patches},
+     doctype="Cashew Import Run",
+     docname=run_name,
+ )
```

For `validate_import`: emit after the full validation pass (one event
carrying the changed rows) rather than per-row mid-loop — cheaper and
the SPA gets one render pass:

```python
# api.py validate_import after the validation loop, before return
+ if changed_rows:
+     frappe.publish_realtime(
+         event="doc_update",
+         message={"doctype": "Cashew Import Run", "name": run_name, "rows": changed_rows},
+         doctype="Cashew Import Run",
+         docname=run_name,
+     )
```

`changed_rows` is built as `validate_import` iterates — each row's
`{ row_idx, validation_status, validation_error_code,
validation_error_message }` payload.

### Throttling (worker post loop)

The worker post loop writes a row, then potentially publishes a
realtime event for each row. At ~1k rows in 30s = ~33 events / sec —
fine. Above that, batch into groups of 25:

```python
# pseudo
buffer = []
for i, row in enumerate(rows):
    process_row(...)
    buffer.append(row_patch_for(row))
    if len(buffer) >= 25 or i == len(rows) - 1:
        frappe.publish_realtime(
            event="doc_update",
            message={"doctype": "Cashew Import Run", "name": run.name, "rows": buffer},
            doctype="Cashew Import Run", docname=run.name,
        )
        buffer.clear()
```

Optimization, not v1 blocker. Plain-per-row is fine for current
volumes; revisit if `frappe.publish_realtime` itself becomes a
bottleneck (it won't at <100 events/sec on a single bench).

---

## Files touched

```
cashew_integration/importer/worker.py                  # EDIT — add _emit_row_update + 5 call sites
cashew_integration/api.py                              # EDIT — emit rows in validate_import +
                                                       #         row_explorer_set_party +
                                                       #         row_explorer_revalidate
                                                       # EDIT — patch 1: api.py L206/L300 → run.db_set
```

No new modules required.

---

## SQL writes — confirm none

The grep at `importer/idempotency.py` shows two `frappe.db.sql` calls.
Both are `SELECT` (read), not `UPDATE`. Confirmed safe:

- `idempotency.py:67` — SELECT existing posted docnames
- `idempotency.py:103` — SELECT to find prior runs

No bare SQL UPDATE in the codebase against `Cashew Import Run` or
`Cashew Import Row`. If a future patch adds one, it MUST add a paired
`frappe.publish_realtime('doc_update', ...)` per this audit.

---

## Acceptance

- [ ] `_emit_row_update` helper exists in `worker.py` and is used at
      all 5 revert/post sites.
- [ ] `validate_import` publishes one parent-run doc_update with all
      changed rows at the end of its loop.
- [ ] `row_explorer_set_party` publishes a parent-run doc_update with
      the affected rows' patches.
- [ ] `row_explorer_revalidate` publishes a parent-run doc_update with
      the affected rows' new validation state.
- [ ] api.py `Cashew Import Run` status writes use `run.db_set(...,
      notify=True)` (patch 1).
- [ ] All existing tests pass.
- [ ] Manual smoke: open the SPA Run Workspace on a queued run; trigger
      a worker (`bench execute cashew_integration.importer.worker.process_run`
      against a test run); rows flip status live without reload; row
      counters update; final `Completed` status flips the page to
      CompletedSummary.
- [ ] Manual smoke: in two browser tabs open the same run; trigger
      `row_explorer_set_party` from one tab; the other tab's row
      updates within ~1s.
- [ ] No `frappe.db.sql("UPDATE …")` against Cashew Import Run /
      Cashew Import Row (grep confirms).

---

## TD calls inside arch envelope (not surfacing)

- **Synthetic parent emission for child-row patches.** Frappe's
  native `doc_update` is per-doc; child rows are part of a doc but
  not directly subscribable. The cleanest path is: emit a
  `doc_update` for the parent run carrying a `rows: [...]` field;
  c008 normalizes this into `{ doc, rows }` for consumers.
- **One emission per write batch** (post loop, validate loop, bulk
  set_party). Better than per-row in tight loops; fine at v1
  volumes.
- **Reuse the existing `doc_update` event name.** Frappe's built-in
  payload listener handles it; no new event type to register.
- **No throttling v1.** Cashew runs are small (hundreds of rows in a
  monthly import); naive per-row emission is fine. The batching
  pseudo-code is documented above for future scale.

---

## Open items (handed off)

- **`frappe.db.set_value` default `notify` behavior in v15 vs v16.**
  Verify on first install; patch 1 is a precaution. If v16 default
  is notify=True, patch 1 is harmless. If v15 default is False (it
  is), patch 1 is required for older deployments.
- **Bulk-emit batching above 25 rows** — promote the pseudo-code to
  real code if Cashew imports grow past 5k rows / minute. Not v1.
- **Optional: synchronous reads in api.py** that don't mutate state
  but the SPA might want to refresh after (e.g. `get_run_progress`
  poll under disconnected state) — these don't need emissions; the
  SPA polls them directly under c008's fallback path.
