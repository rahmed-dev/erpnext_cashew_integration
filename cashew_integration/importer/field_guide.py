"""
Import Row Field Guide — single source of truth for "what does this field mean?"

Authored definitions for every meaningful Cashew Import Row field, grouped by
purpose. Consumed by BOTH surfaces so help text never diverges:
  - Desk: Cashew Import Run form "Field Guide" button (cashew_import_run.js)
  - SPA:  same content via the get_import_row_field_guide whitelisted endpoint

Definitions live here; field LABELS are merged live from the doctype meta at
read time (build_field_guide), so a label rename on the doctype reflects
automatically without editing this file.
"""

# Ordered groups → ordered fieldnames. Drives display order on both surfaces.
FIELD_GUIDE_GROUPS = [
    {
        "group": "From the Cashew CSV",
        "intro": "Raw values read straight from the uploaded export — never changed by the importer.",
        "fields": [
            "row_idx", "raw_account", "txn_date", "raw_txn_time", "month_key",
            "raw_amount", "income_flag", "category", "sub_category",
            "item_label", "title", "note", "source_hash",
        ],
    },
    {
        "group": "Currency & exchange",
        "intro": "How a foreign-currency row is converted into your company's base currency before it posts.",
        "fields": [
            "source_currency", "company_currency", "exchange_rate", "base_amount",
        ],
    },
    {
        "group": "Classification",
        "intro": "How the importer interprets the row and decides which ERP document to create.",
        "fields": ["txn_type", "resolved_route", "transfer_pair_row_idx"],
    },
    {
        "group": "Resolved accounts (where it posts)",
        "intro": "The ledger accounts this row will hit, resolved from your Account & Category mappings.",
        "fields": [
            "resolved_erp_account", "resolved_external_account",
            "resolved_account", "resolved_income_account", "resolved_expense_account",
        ],
    },
    {
        "group": "Party",
        "intro": "The Customer or Supplier a row posts against, when one is required.",
        "fields": [
            "requires_party", "resolved_party_type", "resolved_party", "party_source",
        ],
    },
    {
        "group": "Validation",
        "intro": "Whether the row is allowed to post, and why not if it is blocked.",
        "fields": [
            "validation_status", "validation_severity",
            "validation_error_code", "validation_error_message", "is_duplicate",
        ],
    },
    {
        "group": "Posting result",
        "intro": "Filled in after a successful Queue Run — the ERP document this row produced.",
        "fields": ["posted_doctype", "posted_docname", "posted_gl_date"],
    },
    {
        "group": "Revert",
        "intro": "State after a Revert Run undoes a completed import.",
        "fields": ["revert_status", "revert_error"],
    },
]

# fieldname -> plain-language definition.
FIELD_DEFINITIONS = {
    # From the Cashew CSV
    "row_idx": "Position of this transaction in the uploaded CSV (1-based). A stable handle for fixing or reverting one specific row.",
    "raw_account": "The account name exactly as Cashew wrote it (e.g. \"NSave\", \"Elevate Pay\"). Matched against Cashew Account Mapping to find your ERP cash/bank account.",
    "txn_date": "Transaction date as recorded in Cashew.",
    "raw_txn_time": "Time of day from Cashew, when present. Helps order same-day rows and pair up the two legs of a transfer.",
    "month_key": "YYYY-MM derived from the transaction date — the period bucket this row falls in.",
    "raw_amount": "Amount in the source currency, exactly as written in Cashew (sign follows Cashew's convention).",
    "income_flag": "Cashew's own income/expense marker for the row. One of the inputs used to decide the Transaction Type.",
    "category": "Cashew category. Looked up in Cashew Category Mapping to decide routing and the counter-account.",
    "sub_category": "Cashew sub-category, refining the category lookup.",
    "item_label": "Optional item/label text from Cashew.",
    "title": "Transaction title / payee from Cashew.",
    "note": "Free-text note attached to the transaction in Cashew.",
    "source_hash": "Fingerprint of the raw CSV line. Used for idempotency — detecting whether this exact transaction was already imported.",

    # Currency & exchange
    "source_currency": "Currency of the Raw Amount.",
    "company_currency": "Your ERP company's base (accounting) currency.",
    "exchange_rate": "Rate used to convert Source → Company currency. Fetched when you click Validate Import.",
    "base_amount": "Raw Amount converted to company currency using the Exchange Rate. This is the figure that actually posts to the General Ledger.",

    # Classification
    "txn_type": "How the row is interpreted: Income, Expense, Transfer, External Transfer, Adjustment, Loan Receivable, or Loan Payable. Drives which accounts and which document are used.",
    "resolved_route": "The posting strategy chosen from the Transaction Type — the kind of document that will be created (Journal Entry, Transfer JV, External Transfer JE, Adjustment JE, Loan JE).",
    "transfer_pair_row_idx": "For an internal Transfer, the row index of the matching other leg — money leaving one account is the same event as it arriving in another. Links the two halves.",

    # Resolved accounts
    "resolved_erp_account": "The ERP cash/bank account mapped from Raw Account — the account whose balance this row moves. Resolved from Cashew Account Mapping. If blank, the Raw Account isn't mapped yet.",
    "resolved_external_account": "Only for External Transfer rows. When Cashew names the other side of a transfer inside the row itself (a \"partner\" account) rather than as a separate CSV line, this is the ERP account that partner name maps to — i.e. the second account of the journal entry. Blank means that partner account isn't in Cashew Account Mapping.",
    "resolved_account": "The counter-account resolved from the Category Mapping — the income/expense/other ledger the money flows to or from.",
    "resolved_income_account": "The specific income ledger used when the category resolves to income.",
    "resolved_expense_account": "The specific expense ledger used when the category resolves to an expense.",

    # Party
    "requires_party": "Whether this row must name a Customer or Supplier before it can post (e.g. income needs a Customer, an expense a Supplier). Set by the Category Mapping.",
    "resolved_party_type": "The kind of party this row posts against: Customer, Supplier, or None.",
    "resolved_party": "The actual Customer or Supplier document chosen for this row (picked in the Row Explorer).",
    "party_source": "Where the party came from — a per-row Preview Override, or a Run Default.",

    # Validation
    "validation_status": "Valid, Error, or Skipped — the gate that decides whether this row will post.",
    "validation_severity": "How serious a flagged issue is: Error (blocks posting), Warning, or Info.",
    "validation_error_code": "Machine-readable code for the problem, e.g. CASHEW_ACCOUNT_NOT_MAPPED.",
    "validation_error_message": "Human-readable explanation of why the row is flagged.",
    "is_duplicate": "The row matches a transaction already imported (by source hash / external id). Skipped to avoid double-posting.",

    # Posting result
    "posted_doctype": "The ERP document type created when this row posted: Sales Invoice, Purchase Invoice, or Journal Entry.",
    "posted_docname": "The name of the actual posted document — click through to inspect the GL entry.",
    "posted_gl_date": "The accounting date the document posted on.",

    # Revert
    "revert_status": "State after a Revert Run: Reverted, or Revert-Failed.",
    "revert_error": "Why a revert failed, if it did.",
}


def build_field_guide() -> list[dict]:
    """Return the field guide as ordered groups, with labels merged live from the
    Cashew Import Row doctype meta.

    Shape: ``[{"group", "intro", "fields": [{"fieldname", "label", "definition"}]}]``
    Identical payload for the Desk button and the SPA — single source of truth.
    """
    import frappe

    meta = frappe.get_meta("Cashew Import Row")
    label_by_name = {df.fieldname: (df.label or df.fieldname) for df in meta.fields}

    guide = []
    for grp in FIELD_GUIDE_GROUPS:
        fields = []
        for fieldname in grp["fields"]:
            definition = FIELD_DEFINITIONS.get(fieldname)
            if not definition:
                continue
            fields.append({
                "fieldname": fieldname,
                "label": label_by_name.get(fieldname, fieldname),
                "definition": definition,
            })
        if fields:
            guide.append({
                "group": grp["group"],
                "intro": grp.get("intro", ""),
                "fields": fields,
            })
    return guide
