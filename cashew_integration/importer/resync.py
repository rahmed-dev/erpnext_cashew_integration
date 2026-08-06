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

Resync has its own lifecycle, deliberately placed OUTSIDE the worker's
transaction-type switch:

    screen_resyncs()      before anything is written — refuse what cannot be replaced
    <the ordinary post loop, which knows nothing about resync>
    apply_supersessions()  after everything is posted — cancel what was replaced

The first version of this module hung the cancel-and-repost off one branch of that
type switch, which the worker reached only for non-Transfer rows. An edited transfer
leg therefore posted a second JV and left the stale one submitted — the exact
double-count this module exists to prevent. Splitting the lifecycle in two means
transfers, external transfers, loans and invoices all get the behaviour for free, and
nothing is cancelled until the whole run has posted successfully.

Only rows imported from a SQLite backup carry a ``source_pk``. CSV-era rows have none
and take the unchanged hash-only path — their history is not covered.
"""

import frappe

from cashew_integration.importer.errors import set_row_validation_error


# Written to Cashew Import Row.revert_status by a resync.
RESYNCED = "Resynced"        # this row replaced an earlier posting
SUPERSEDED = "Superseded"    # this row's document was cancelled and replaced
SUPERSEDE_FAILED = "Supersede-Failed"  # replacement posted, original still live


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

    tagged += _propagate_to_transfer_partners(rows, prior_by_pk)
    return tagged


def _propagate_to_transfer_partners(rows: list[dict], prior_by_pk: dict) -> int:
    """Tag the other leg of a transfer pair whenever one leg is tagged.

    A transfer's two legs share a single Journal Entry, but they hash separately.
    Editing only the source leg's amount leaves the destination leg's hash untouched,
    so the hash guard would skip it — stranding the tagged leg with no partner and
    failing it as TRANSFER_PAIR_INCOMPLETE while the stale JV stayed submitted. The
    pair is replaced as a unit or not at all.
    """
    by_idx = {r["row_idx"]: r for r in rows if r.get("row_idx")}
    extra = 0

    for row in list(rows):
        if not row.get("_resync_of"):
            continue
        partner = by_idx.get(row.get("transfer_pair_row_idx"))
        if partner is None or partner.get("_resync_of"):
            continue
        if partner.get("validation_status") in ("Error", "Skipped"):
            continue
        # The partner's own prior row when it has one, else the tagged leg's — both
        # point at the same Journal Entry, which is what apply_supersessions cancels.
        partner["_resync_of"] = (
            prior_by_pk.get(partner.get("source_pk")) or row["_resync_of"]
        )
        extra += 1

    return extra


# ── phase 1: screen, before any GL is written ──────────────────────────────────

def screen_resyncs(rows: list[dict], run) -> None:
    """Decide which tagged rows may supersede, *before* the posting loop runs.

    A tag is dropped when there is nothing live to replace — that row is an ordinary
    new posting and must not be counted or logged as a resync it never performed. A
    tag is refused, with the row Errored, when the document it would replace sits in
    a closed period: the run would otherwise post the corrected figure and then be
    unable to cancel the stale one, leaving both in the ledger.
    """
    for row in list(rows):
        prior = row.get("_resync_of")
        if not prior:
            continue

        doctype = prior.get("posted_doctype") or "Journal Entry"
        docname = prior.get("posted_docname")

        if not docname or not frappe.db.exists(doctype, docname):
            # Deleted, or reverted before this run started. Nothing to supersede.
            row.pop("_resync_of", None)
            continue

        docstatus, posting_date = frappe.db.get_value(
            doctype, docname, ["docstatus", "posting_date"]
        )
        if docstatus != 1:
            # Already cancelled or still a draft: no GL impact to replace.
            row.pop("_resync_of", None)
            continue

        closed = _period_closed(posting_date, run.company)
        if closed:
            _refuse_pair(
                rows, row, "RESYNC_PERIOD_CLOSED",
                f"{doctype} {docname} was edited in Cashew, but {posting_date} falls "
                f"in a closed period ({closed}). The ledger still holds the pre-edit "
                "figure. Reopen the period or post a manual adjustment.",
            )


def _refuse_pair(rows: list[dict], row: dict, code: str, message: str) -> None:
    """Error *row*, and its transfer partner if it has one, with the same cause.

    Erroring one leg alone would leave the other to fail later as
    TRANSFER_PAIR_INCOMPLETE, which names a symptom instead of the actual reason.
    """
    set_row_validation_error(row, code, message)
    row.pop("_resync_of", None)

    partner_idx = row.get("transfer_pair_row_idx")
    if not partner_idx:
        return
    for other in rows:
        if other.get("row_idx") == partner_idx:
            set_row_validation_error(other, code, message)
            other.pop("_resync_of", None)
            break


# ── phase 2: supersede, after everything has posted ────────────────────────────

def apply_supersessions(rows: list[dict], run) -> tuple[int, int]:
    """Cancel the documents replaced by this run's postings.

    Returns ``(superseded, failed)``. Runs only after the whole posting loop has
    finished, so the replacement provably exists before anything is cancelled —
    the period is never left with neither entry.

    A failure here is the one outcome that puts two live documents in the ledger for
    a single transaction, so it is stamped on the row, counted as a failure (which
    fails the run) and logged. It must never pass quietly.
    """
    superseded = failed = 0
    seen: dict[tuple[str, str], str] = {}

    for row in rows:
        prior = row.get("_resync_of")
        if not prior or not row.get("posted_docname"):
            continue

        doctype = prior.get("posted_doctype") or "Journal Entry"
        docname = prior.get("posted_docname")
        key = (doctype, docname)

        # A transfer pair's two legs share one Journal Entry — cancel it once, then
        # stamp the second leg from the first leg's result.
        if key in seen:
            _stamp_successor(row, doctype, docname, prior)
            continue

        try:
            _cancel_superseded(doctype, docname, run)
        except Exception as exc:
            frappe.log_error(
                frappe.get_traceback(),
                f"Cashew Supersede Failed: run={run.name} doc={docname}",
            )
            row["revert_status"] = SUPERSEDE_FAILED
            row["revert_error"] = (
                f"{row['posted_docname']} was posted to replace {doctype} {docname}, "
                f"but {docname} could not be cancelled: {exc}. BOTH are now live and "
                "this transaction is counted twice — cancel one by hand."
            )[:500]
            failed += 1
            continue

        seen[key] = row["posted_docname"]
        _stamp_prior(prior, row.get("posted_doctype") or "Journal Entry",
                     row["posted_docname"])
        _stamp_successor(row, doctype, docname, prior)
        superseded += 1

    return superseded, failed


def _cancel_superseded(doctype: str, docname: str, run) -> None:
    """Cancel a replaced document, flagged as the app's own cancel.

    ``cashew_reverting`` keeps reconcile.on_document_cancelled from reporting this as
    an external cancellation — it is a recorded supersession, not drift.
    """
    frappe.flags.cashew_reverting = run.name
    try:
        frappe.get_doc(doctype, docname).cancel()
    finally:
        frappe.flags.cashew_reverting = None


def _stamp_successor(row: dict, doctype: str, docname: str, prior: dict) -> None:
    row["revert_status"] = RESYNCED
    row["supersedes"] = docname
    row["revert_error"] = (
        f"Source transaction edited in Cashew. Replaces {doctype} {docname} "
        f"(row {prior.get('row_idx')} of {prior.get('parent')}), now cancelled."
    )[:500]


def _stamp_prior(prior: dict, new_doctype: str, new_docname: str) -> None:
    """Record the successor on the superseded row, as a document name.

    ``superseded_by`` is stored rather than inferred so reconcile can *verify* the
    lineage: a cancelled document whose replacement is live is not drift, but one
    whose replacement has itself gone is. A bare status string cannot tell them apart.
    """
    frappe.db.set_value(
        "Cashew Import Row", prior["name"],
        {
            "revert_status": SUPERSEDED,
            "superseded_by": new_docname,
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
