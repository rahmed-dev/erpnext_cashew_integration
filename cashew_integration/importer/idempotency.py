"""
C006 — Idempotency Guard

Checks whether a row (identified by source_hash + company) has already been
posted in any prior run, and marks it Skipped if so.

Primary check:  query Cashew Import Row for (source_hash, company) where
                posted_docname is not null.
Secondary check: query the cashew_row_hash custom field on SI/PI/JE documents.

Transfer pairs: idempotency is checked on the source leg's hash.
If the source leg is a duplicate, both legs are marked Skipped.
"""

import frappe

from cashew_integration.importer.errors import prefix_with_row_idx
from cashew_integration.importer.resync import mark_changed_rows


# ── public entry point ─────────────────────────────────────────────────────────

def apply_idempotency_guard(rows: list[dict], run) -> None:
    """
    Mark already-posted rows as Skipped.
    Mutates *rows* in-place.  Transfer pair partner is also skipped when
    the source leg is found to be a duplicate.
    """
    company   = run.company
    run_name  = run.name

    # Tag edited-upstream rows FIRST. A Cashew edit changes source_hash, so an edited
    # transaction would otherwise sail past the hash check as if it were new, and its
    # stale original would stay submitted — the ledger would then hold both figures.
    # Rows tagged here carry `_resync_of` and must not be skipped below: the hash they
    # now carry is genuinely absent from the ledger.
    mark_changed_rows(rows, run)

    # Build lookup: source_hash -> (posted_doctype, posted_docname)
    # from existing Cashew Import Row records in other (completed) runs
    existing = _fetch_posted_hashes(company, run_name)
    # Augment with secondary check on the ERP documents themselves
    si_pi_je_dupes = _fetch_erp_document_hashes(rows)
    existing.update(si_pi_je_dupes)

    by_idx = {r["row_idx"]: r for r in rows}

    for row in rows:
        if row.get("validation_status") in ("Error", "Skipped"):
            continue
        if row.get("_resync_of"):
            continue  # edited upstream — resync replaces the original, never a skip

        h = row.get("source_hash")
        if h and h in existing:
            posted_dt, posted_dn = existing[h]
            _mark_skipped(row, posted_dt, posted_dn)

            # Propagate skip to transfer pair partner
            partner_idx = row.get("transfer_pair_row_idx")
            if partner_idx:
                partner = by_idx.get(partner_idx)
                if partner and partner.get("validation_status") not in ("Error", "Skipped"):
                    _mark_skipped(partner, posted_dt, posted_dn)


# ── database lookups ───────────────────────────────────────────────────────────

def _fetch_posted_hashes(company: str, exclude_run: str) -> dict[str, tuple[str, str]]:
    """
    Return {source_hash: (posted_doctype, posted_docname)} for rows that
    were already posted in any run for *company*, excluding the current run.

    We join through Cashew Import Run to filter by company.
    """
    rows = frappe.db.sql(
        """
        SELECT
            r.source_hash,
            r.posted_doctype,
            r.posted_docname
        FROM `tabCashew Import Row` r
        JOIN `tabCashew Import Run` p ON p.name = r.parent
        WHERE p.company = %s
          AND p.name    != %s
          AND r.posted_docname IS NOT NULL
          AND r.posted_docname != ''
          AND r.source_hash IS NOT NULL
          AND r.source_hash != ''
        """,
        (company, exclude_run),
        as_dict=True,
    )
    return {r["source_hash"]: (r["posted_doctype"], r["posted_docname"]) for r in rows}


def _fetch_erp_document_hashes(rows: list[dict]) -> dict[str, tuple[str, str]]:
    """
    Secondary check: query the cashew_row_hash custom field on SI, PI, JE.
    Only checks hashes that appear in the current batch to keep the query narrow.
    """
    hashes = list({r["source_hash"] for r in rows if r.get("source_hash")})
    if not hashes:
        return {}

    result = {}
    placeholders = ", ".join(["%s"] * len(hashes))

    for doctype in ("Sales Invoice", "Purchase Invoice", "Journal Entry"):
        table = f"tab{doctype}"
        try:
            docs = frappe.db.sql(
                f"""
                SELECT name, cashew_row_hash
                FROM `{table}`
                WHERE cashew_row_hash IN ({placeholders})
                  AND docstatus = 1
                """,
                hashes,
                as_dict=True,
            )
            for d in docs:
                if d["cashew_row_hash"] not in result:
                    result[d["cashew_row_hash"]] = (doctype, d["name"])
        except Exception:
            # Custom field may not exist yet on first install; ignore gracefully
            pass

    return result


# ── helpers ────────────────────────────────────────────────────────────────────

def _mark_skipped(row: dict, posted_doctype: str, posted_docname: str) -> None:
    row["validation_status"]        = "Skipped"
    row["is_duplicate"]             = 1
    row["posted_doctype"]           = posted_doctype
    row["posted_docname"]           = posted_docname
    row["validation_error_message"] = prefix_with_row_idx(
        row,
        f"Duplicate — already posted as {posted_doctype} {posted_docname}.",
    )
