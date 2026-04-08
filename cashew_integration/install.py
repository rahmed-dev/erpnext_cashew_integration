"""
C009 — Install-Time Setup

Runs after app installation (after_install hook).
Custom fields are shipped as fixtures (fixtures/custom_field.json) and applied
automatically by Frappe during install/migrate — no Python required for that.

This module only handles things fixtures cannot do: creating the Cashew Settings
singleton document if it doesn't already exist.
"""

import frappe


def after_install():
    _create_cashew_settings()
    frappe.db.commit()


def _create_cashew_settings():
    if not frappe.db.exists("Cashew Settings", "Cashew Settings"):
        frappe.get_doc({"doctype": "Cashew Settings"}).insert(ignore_permissions=True)
