"""
C009 — Install-Time Setup

Runs after app installation (after_install hook).
Custom fields are shipped as fixtures (fixtures/custom_field.json) and applied
automatically by Frappe during install/migrate — no Python required for that.

This module handles:
  1. Creating the Cashew Settings singleton if it doesn't exist.
  2. Seeding default account and category mappings from packaged defaults.
     If no company or Chart of Accounts exists yet (fresh site), setup is
     skipped gracefully and can be re-run later via api.setup_from_csv or
     by calling cashew_integration.setup.run_setup() from the bench console.
"""

import frappe


def after_install():
    _create_cashew_settings()
    _seed_default_mappings()
    frappe.db.commit()


def _create_cashew_settings():
    # For Single DocTypes, frappe.db.exists() always returns True (Frappe v16 shortcut).
    # Check tabSingles directly to see if the singleton has ever been saved.
    if not frappe.db.get_singles_dict("Cashew Settings"):
        frappe.get_doc({"doctype": "Cashew Settings"}).save(ignore_permissions=True)


def _seed_default_mappings():
    from cashew_integration.setup import run_setup
    try:
        result = run_setup()
        if result.get("skipped"):
            frappe.logger().info(
                "Cashew Integration: default mapping seed skipped — %s",
                result.get("reason"),
            )
        else:
            frappe.logger().info(
                "Cashew Integration: seeded %d accounts, %d categories.",
                result["accounts_added"],
                result["categories_added"],
            )
    except Exception:
        # Don't block installation if CoA isn't ready yet.
        frappe.logger().warning(
            "Cashew Integration: default mapping seed failed — "
            "run cashew_integration.setup.run_setup() once your Chart of Accounts is ready.\n%s",
            frappe.get_traceback(),
        )
