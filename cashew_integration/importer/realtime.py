"""
Realtime emission helpers for Cashew Import Run / Row updates.

Frappe doesn't emit per-child-row events on `Cashew Import Row` mutations.
The SPA (f010 c008) subscribes to the parent `Cashew Import Run` and
expects a synthetic `doc_update` event carrying changed-row patches under
a `rows` field.
"""

import frappe


def emit_row_update(run_name: str, row_patch: dict) -> None:
    """Publish a synthetic parent-run doc_update carrying a single row patch.

    `row_patch` must include `row_idx` plus any subset of the mutated
    row fields (validation_status, posted_doctype, revert_status, ...).
    Multiple row updates per write batch may be coalesced via
    `emit_row_update_batch`.
    """
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


def emit_row_update_batch(run_name: str, row_patches: list[dict]) -> None:
    """Coalesce multiple row patches into one realtime event."""
    if not row_patches:
        return
    frappe.publish_realtime(
        event="doc_update",
        message={
            "doctype": "Cashew Import Run",
            "name": run_name,
            "rows": row_patches,
        },
        doctype="Cashew Import Run",
        docname=run_name,
    )


def emit_run_progress(run_name: str, fields: dict) -> None:
    """Publish a parent-run `doc_update` carrying changed run-level fields.

    Frappe's own `notify_update` (fired by `db_set(notify=True)`) publishes a
    `doc_update` whose payload is only `{modified, doctype, name}` — it does NOT
    carry the changed field values.  So the SPA's `patchDoc(event)` learns only
    `modified` and the displayed status / counters stay frozen at "Queued" until
    a full reload (page refresh).  This helper sends the actual values
    (status, rows_posted, …) so progress and completion update live.

    `fields` is a flat dict of the changed run-level fields.
    """
    if not fields:
        return
    frappe.publish_realtime(
        event="doc_update",
        message={
            "doctype": "Cashew Import Run",
            "name": run_name,
            **fields,
        },
        doctype="Cashew Import Run",
        docname=run_name,
    )
