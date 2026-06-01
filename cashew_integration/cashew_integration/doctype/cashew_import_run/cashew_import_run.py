import frappe
from frappe.model.document import Document


class CashewImportRun(Document):

    def on_trash(self):
        # Blocked only when the run has live journal entries (Completed /
        # Revert-Failed) or is mid-flight (Queued / Processing / Reverting).
        # Everything else is safe to delete — Draft/Parsed/Validated/Failed/
        # Cancelled never posted, and Reverted has already had its JEs cancelled
        # — so a user can discard a parsed-but-not-posted import and restart.
        # NB: rows_posted is a lifetime counter (stays set after revert), so it
        # is not a reliable "has live GL" signal; status is.
        _UNDELETABLE_STATUSES = {
            "Queued", "Processing", "Reverting", "Completed", "Revert-Failed",
        }
        if self.status in _UNDELETABLE_STATUSES:
            frappe.throw(
                f"Cannot delete Import Run {self.name} with status '{self.status}'. "
                "Wait for any in-flight processing to finish and revert posted "
                "journal entries before deleting.",
                frappe.PermissionError,
            )
