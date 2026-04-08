"""
C008 — Diagnostics CSV

Generates a per-row diagnostics CSV at import run completion.
The file is saved as a private attachment and its path stored on
``run.diagnostics_file``.
"""

import csv
import io
import os

import frappe
from frappe.utils.file_manager import save_file

_COLUMNS = [
    "row_idx",
    "txn_date",
    "raw_account",
    "amount",
    "currency",
    "base_amount",
    "exchange_rate",
    "category",
    "sub_category",
    "title",
    "txn_type",
    "resolved_route",
    "resolved_account",
    "resolved_income_account",
    "resolved_expense_account",
    "resolved_erp_account",
    "resolved_external_account",
    "resolved_party",
    "party_source",
    "transfer_pair_row_idx",
    "validation_status",
    "error_code",
    "error_message",
    "posted_doctype",
    "posted_docname",
    "is_duplicate",
    "review_recommended",
]


def generate_diagnostics_csv(rows: list[dict], run) -> str:
    """
    Write a diagnostics CSV for *rows*, attach it to *run*, and return
    the file URL stored in ``run.diagnostics_file``.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()

    for row in rows:
        writer.writerow(_to_csv_row(row))

    filename = f"cashew-diagnostics-{run.name}.csv"
    content  = buf.getvalue().encode("utf-8")

    file_doc = save_file(
        fname=filename,
        content=content,
        dt="Cashew Import Run",
        dn=run.name,
        is_private=1,
    )
    return file_doc.file_url


def _to_csv_row(row: dict) -> dict:
    return {
        "row_idx":                  row.get("row_idx"),
        "txn_date":                 row.get("txn_date"),
        "raw_account":              row.get("raw_account"),
        "amount":                   row.get("raw_amount"),
        "currency":                 row.get("source_currency"),
        "base_amount":              row.get("base_amount"),
        "exchange_rate":            row.get("exchange_rate"),
        "category":                 row.get("category"),
        "sub_category":             row.get("sub_category"),
        "title":                    row.get("title"),
        "txn_type":                 row.get("txn_type"),
        "resolved_route":           row.get("resolved_route"),
        "resolved_account":         row.get("resolved_account"),
        "resolved_income_account":  row.get("resolved_income_account"),
        "resolved_expense_account": row.get("resolved_expense_account"),
        "resolved_erp_account":     row.get("resolved_erp_account"),
        "resolved_external_account": row.get("resolved_external_account"),
        "resolved_party":           row.get("resolved_party"),
        "party_source":             row.get("party_source"),
        "transfer_pair_row_idx":    row.get("transfer_pair_row_idx"),
        "validation_status":        row.get("validation_status"),
        "error_code":               row.get("validation_error_code"),
        "error_message":            row.get("validation_error_message"),
        "posted_doctype":           row.get("posted_doctype"),
        "posted_docname":           row.get("posted_docname"),
        "is_duplicate":             1 if row.get("is_duplicate") else 0,
        "review_recommended":       1 if row.get("txn_type") == "Adjustment" else 0,
    }
