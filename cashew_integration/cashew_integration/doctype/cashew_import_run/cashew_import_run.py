import frappe
from frappe.model.document import Document


_LIFECYCLE_FIELDS = (
    "rows_total", "rows_valid", "rows_posted", "rows_failed", "rows_skipped",
)
_RUN_STATE_FIELDS = (
    "started_on", "finished_on", "queued_job_id", "diagnostics_file",
    "period_start", "period_end",
)


class CashewImportRun(Document):

    def validate(self):
        self._force_new_run_to_draft()

    def _force_new_run_to_draft(self):
        """A run that has never executed must not claim it has.

        Desk's Duplicate copies field values verbatim. Before this guard, that
        produced runs carrying another run's status, counters and start/finish
        timestamps — a document reporting 54 posted rows that had posted nothing,
        with a `started_on` earlier than its own `creation`. `no_copy` on those
        fields is the first line of defence; this is the second, and also covers
        API callers that set the fields directly.
        """
        # `creation`, not `is_new()`: the latter reads the `__islocal` flag, which
        # is only set on the insert path and is None for a document built
        # straight from a dict — the exact shape a duplicate arrives in.
        if self.get("creation"):
            return

        self.status = "Draft"
        for field in _LIFECYCLE_FIELDS:
            self.set(field, 0)
        for field in _RUN_STATE_FIELDS:
            self.set(field, None)

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
