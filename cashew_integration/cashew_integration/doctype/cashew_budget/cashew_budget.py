# Copyright (c) 2026, riz, Email: ra9496300@gmail.com
# MIT License (MIT)

import frappe
from frappe.model.document import Document

from cashew_integration.dashboard_series import _KNOWN_REOCCURRENCES


class CashewBudget(Document):
    """A Cashew budget (spending limit or savings goal), mirrored into ERPNext.

    Reference data, not a posting. Budgets are imported outside the row pipeline
    (see ``importer/budgets.py``): they touch no run counters, cannot fail a run,
    and a revert does not remove them.

    Actuals are never stored here. They are computed from GL Entry against the
    resolved scope, so a budget whose scope is not fully mapped is refused at
    import rather than imported with a hole in it.
    """

    def validate(self):
        self.period_length = int(self.period_length or 1) or 1

        # The dashboard raises on an unrecognised reoccurrence rather than
        # bucketing it as monthly. Refusing it here as well means a bad value can
        # never reach the chart layer through a hand-edited document either.
        if self.reoccurrence not in _KNOWN_REOCCURRENCES:
            frappe.throw(
                frappe._("Unrecognised budget reoccurrence {0}. Known values: {1}.").format(
                    self.reoccurrence, ", ".join(sorted(_KNOWN_REOCCURRENCES))
                )
            )
