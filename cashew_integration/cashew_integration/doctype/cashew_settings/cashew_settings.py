# Copyright (c) 2026, riz, Email: ra9496300@gmail.com
# MIT License (MIT)

import re

import frappe
from frappe import _
from frappe.model.document import Document

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class CashewSettings(Document):
    """Singleton DocType for Cashew Settings - Global configuration for Cashew Integration"""

    def validate(self):
        self._validate_unique_account_names()
        self._validate_unique_category_pairs()
        self._validate_accent_color()

    def _validate_accent_color(self):
        if self.accent_color == "Custom":
            value = (self.accent_color_custom or "").strip()
            if not _HEX_RE.match(value):
                frappe.throw(
                    _("Custom Accent Color must be a 6-digit hex like #3b82f6"),
                    title=_("Invalid Accent Color"),
                )
            self.accent_color_custom = value
        else:
            self.accent_color_custom = None

    def _validate_unique_account_names(self):
        seen = set()
        for i, row in enumerate(self.cashew_account_mapping or [], start=1):
            name = (row.cashew_account_name or "").strip()
            if not name:
                continue
            if name in seen:
                frappe.throw(
                    f"Duplicate Cashew Account Name '{name}' in Account Mapping row {i}. "
                    "Each account name must be unique.",
                    frappe.ValidationError,
                    title="Duplicate Account Name",
                )
            seen.add(name)

    def _validate_unique_category_pairs(self):
        seen = set()
        for i, row in enumerate(self.cashew_category_mapping or [], start=1):
            cat = (row.cashew_category or "").strip()
            sub = (row.cashew_sub_category or "").strip()
            if not cat:
                continue
            key = (cat, sub)
            if key in seen:
                display = f"('{cat}', '{sub}')" if sub else f"('{cat}', '')"
                frappe.throw(
                    f"Duplicate category pair {display} in Category Mapping row {i}. "
                    "Each (Category, Sub Category) pair must be unique.",
                    frappe.ValidationError,
                    title="Duplicate Category Pair",
                )
            seen.add(key)
