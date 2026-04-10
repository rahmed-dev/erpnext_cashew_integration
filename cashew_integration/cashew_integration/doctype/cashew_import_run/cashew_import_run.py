import frappe
from frappe.model.document import Document


class CashewImportRun(Document):

    def on_trash(self):
        _DELETABLE_STATUSES = {"Draft", "Reverted"}
        if self.status not in _DELETABLE_STATUSES:
            frappe.throw(
                f"Cannot delete Import Run {self.name} with status '{self.status}'. "
                "Only Draft or fully Reverted runs can be deleted.",
                frappe.PermissionError,
            )
