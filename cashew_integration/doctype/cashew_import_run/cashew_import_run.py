import frappe
from frappe.model.document import Document


class CashewImportRun(Document):

    def on_trash(self):
        if self.status != "Draft":
            frappe.throw(
                f"Cannot delete Import Run {self.name} once it has been started (status: {self.status}).",
                frappe.PermissionError,
            )
