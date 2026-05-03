# Copyright (c) 2026, riz, Email: ra9496300@gmail.com
# MIT License (MIT)

import frappe
from frappe.model.document import Document

from cashew_integration.importer.validation import (
    check_category_account_class,
    check_loan_account_class_exists,
)


class CashewCategoryMapping(Document):
    """Child table of Cashew Settings - Maps Cashew categories to ERPNext posting routes"""

    def validate(self):
        msg = check_loan_account_class_exists(self.category_type)
        if msg:
            frappe.throw(msg)

        msg = check_category_account_class(self.category_type, self.default_account)
        if msg:
            frappe.throw(msg)
