"""
Resync of Cashew transactions that were edited after they were imported.

``source_hash`` describes a transaction's *content*, so editing it in Cashew produces
a different hash — and the hash-keyed idempotency guard then reads the edited row as
brand new rather than as a revision of one already in the ledger. Combined with the
reader's old created-date-only window, an edit to an older transaction was invisible:
ERPNext kept the pre-edit figure indefinitely. A loan edited from 150,000.00 down to
148,674.00 on 2026-07-07 sat in the ledger at 150,000.00, and because the 1,326.00 the
user split off was itself imported, the difference was counted twice.

``source_pk`` (Cashew ``transaction_pk``) is stable across edits. Pairing it with
``source_hash`` gives the three-way answer the importer needs:

===================  =============  ==================================
source_pk            source_hash    meaning
===================  =============  ==================================
unknown              --             new transaction, post it
known                same           already posted, skip (idempotent)
known                different      EDITED upstream, resync it
===================  =============  ==================================

A resync cancels the stale document and posts a replacement, because the user chose
correction-during-import over flag-and-wait. That makes a routine import capable of
rewriting submitted GL, so every guard below fails the row rather than raising, and
the original document is never cancelled unless its replacement can actually be
written.

Only rows imported from a SQLite backup carry a ``source_pk``. CSV-era rows have none
and take the unchanged hash-only path — their history is not covered.
"""

import frappe

from cashew_integration.importer.errors import set_row_validation_error


# Written to Cashew Import Row.revert_status by a resync.
RESYNCED = "Resynced"        # this row replaced an earlier posting
SUPERSEDED = "Superseded"    # this row's document was cancelled and replaced


# ── detection ──────────────────────────────────────────────────────────────────

def find_prior_postings(rows: list[dict], run) -> dict[str, dict]:
    """Return ``{source_pk: prior_row}`` for pks in *rows* already posted elsewhere.

    Mirrors ``idempotency._fetch_posted_hashes``: joins through Cashew Import Run so
    the lookup is scoped to the company, and excludes the current run.
    """
    pks = list({r.get("source_pk") for r in rows if r.get("source_pk")})
    if not pks:
        return {}

    placeholders = ", ".join(["%s"] * len(pks))
    prior = frappe.db.sql(
        f"""
        SELECT r.name, r.source_pk, r.source_hash, r.row_idx,
               r.posted_doctype, r.posted_docname, r.parent
        FROM `tabCashew Import Row` r
        JOIN `tabCashew Import Run` p ON p.name = r.parent
        WHERE p.company = %s
          AND p.name    != %s
          AND r.source_pk IN ({placeholders})
          AND r.posted_docname IS NOT NULL
          AND r.posted_docname != ''
        ORDER BY r.modified ASC
        """,
        [run.company, run.name, *pks],
        as_dict=True,
    )
    # ORDER BY modified ASC + plain assignment leaves the most recent posting per pk,
    # which is the one whose document is actually live after any earlier resync.
    return {r["source_pk"]: r for r in prior}


def mark_changed_rows(rows: list[dict], run) -> int:
    """Tag rows whose source transaction was edited since it was posted.

    Sets ``row['_resync_of']`` (private, never persisted) and returns how many were
    tagged. Rows already Errored or Skipped are left alone.
    """
    prior_by_pk = find_prior_postings(rows, run)
    if not prior_by_pk:
        return 0

    tagged = 0
    for row in rows:
        if row.get("validation_status") in ("Error", "Skipped"):
            continue
        pk = row.get("source_pk")
        if not pk:
            continue
        prior = prior_by_pk.get(pk)
        if not prior:
            continue
        if prior["source_hash"] == row.get("source_hash"):
            continue  # unchanged — the hash guard will skip it as a duplicate
        row["_resync_of"] = prior
        tagged += 1

    return tagged


# ── application ────────────────────────────────────────────────────────────────

def apply_resync(row: dict, run) -> tuple[str, str]:
    """Cancel the stale document for *row* and post its replacement.

    Returns ``(posted_doctype, posted_docname)``, or ``("", "")`` when a guard
    refused. Guards mark the row Errored rather than raising so one bad row cannot
    abort the whole run.
    """
    # Imported here rather than at module scope: posting imports mapping, which
    # imports this module's siblings, and a top-level import closes the cycle.
    from cashew_integration.importer.posting import post_row

    prior = row.get("_resync_of") or {}
    doctype = prior.get("posted_doctype") or "Journal Entry"
    docname = prior.get("posted_docname")

    if not docname or not frappe.db.exists(doctype, docname):
        # Nothing live to replace — post as new. Not an error: the document may have
        # been deleted, or reverted before this run started.
        return post_row(row, run)

    docstatus, posting_date = frappe.db.get_value(
        doctype, docname, ["docstatus", "posting_date"]
    )

    if docstatus != 1:
        # Already cancelled or still draft: it has no GL impact to replace.
        return post_row(row, run)

    closed = _period_closed(posting_date, run.company)
    if closed:
        set_row_validation_error(
            row, "RESYNC_PERIOD_CLOSED",
            f"{doctype} {docname} was edited in Cashew, but {posting_date} falls in a "
            f"closed period ({closed}). The ledger still holds the pre-edit figure. "
            "Reopen the period or post a manual adjustment.",
        )
        return "", ""

    # Post the replacement FIRST. Cancelling first and failing to repost would leave
    # the period with neither entry, which is worse than the stale figure this fixes.
    try:
        new_doctype, new_docname = post_row(row, run)
    except Exception as exc:
        set_row_validation_error(
            row, "RESYNC_REPOST_FAILED",
            f"{doctype} {docname} was edited in Cashew but the replacement could not "
            f"be posted: {exc}. The original is untouched and still submitted.",
        )
        return "", ""

    if not new_doctype:
        set_row_validation_error(
            row, "RESYNC_REPOST_FAILED",
            f"{doctype} {docname} was edited in Cashew but the replacement could not "
            "be posted. The original is untouched and still submitted.",
        )
        return "", ""

    # Our own cancel — the flag keeps reconcile.on_document_cancelled from reporting
    # it as an external cancellation.
    frappe.flags.cashew_reverting = run.name
    try:
        frappe.get_doc(doctype, docname).cancel()
    finally:
        frappe.flags.cashew_reverting = None

    _stamp_prior(prior, new_doctype, new_docname)
    row["revert_status"] = RESYNCED
    row["revert_error"] = (
        f"Source transaction edited in Cashew. Replaces {doctype} {docname} "
        f"(row {prior.get('row_idx')} of {prior.get('parent')}), now cancelled."
    )[:500]

    return new_doctype, new_docname


def _stamp_prior(prior: dict, new_doctype: str, new_docname: str) -> None:
    frappe.db.set_value(
        "Cashew Import Row", prior["name"],
        {
            "revert_status": SUPERSEDED,
            "revert_error": (
                f"Source transaction was edited in Cashew after this row posted. "
                f"{prior.get('posted_doctype') or 'Journal Entry'} "
                f"{prior.get('posted_docname')} was cancelled and replaced by "
                f"{new_doctype} {new_docname}."
            )[:500],
        },
        update_modified=False,
    )


def _period_closed(posting_date, company: str) -> str | None:
    """Return a reason string when *posting_date* is not writable, else None."""
    if not posting_date:
        return None

    closed_year = frappe.db.sql(
        """
        SELECT fy.name
        FROM `tabFiscal Year` fy
        JOIN `tabFiscal Year Company` fyc ON fyc.parent = fy.name
        WHERE fyc.company = %s
          AND fy.disabled = 1
          AND %s BETWEEN fy.year_start_date AND fy.year_end_date
        LIMIT 1
        """,
        (company, posting_date),
    )
    if closed_year:
        return f"disabled Fiscal Year {closed_year[0][0]}"

    pcv = frappe.db.get_value(
        "Period Closing Voucher",
        {"company": company, "docstatus": 1, "posting_date": [">=", posting_date]},
        "name",
    )
    if pcv:
        return f"Period Closing Voucher {pcv}"

    return None
