"""Web page entry for the Cashew SPA (f010).

Runs on every /cashew/* request via the website_route_rule in hooks.py.
Handles auth + role gate, then injects the boot dict consumed by
`window.boot` in the Vue shell (c004).
"""

import frappe
from frappe import _
from frappe.utils import get_first_day, get_system_timezone, getdate

from cashew_integration.pwa import resolve_theme_color

no_cache = 1


def get_context():
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/cashew"
		raise frappe.Redirect

	if not check_app_permission():
		raise frappe.PermissionError(_("You don't have access to Cashew."))

	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = frappe.sessions.get_csrf_token()
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw("This method is only meant for developer mode")
	if not check_app_permission():
		raise frappe.PermissionError(_("You don't have access to Cashew."))
	return get_boot()


def check_app_permission():
	"""True if session user holds the role gate (D3.a)."""
	roles = frappe.get_roles(frappe.session.user)
	return "System Manager" in roles or "Accounts Manager" in roles


def _current_fiscal_year(today):
	"""The fiscal year containing `today`, as {name, start, end}, or None.

	`get_fiscal_year` throws when no Fiscal Year record covers the date, which
	is a legitimate state on a site that has not set one up yet and is not a
	reason to fail the whole page. The client falls back to the calendar year
	when this comes back None, and says so in the period label.
	"""
	try:
		from erpnext.accounts.utils import get_fiscal_year

		name, start, end = get_fiscal_year(today, as_dict=False)
		return {"name": name, "start": str(start), "end": str(end)}
	except Exception:
		return None


def get_boot():
	user = frappe.session.user
	user_doc = frappe.get_cached_doc("User", user)
	settings = frappe.get_cached_doc("Cashew Settings", "Cashew Settings")
	today = getdate()
	period_start = get_first_day(today)

	return frappe._dict({
		# Frappe baseline
		"frappe_version": frappe.__version__,
		"site_name": frappe.local.site,
		"read_only_mode": frappe.flags.read_only,
		"system_timezone": get_system_timezone(),

		# Session + auth (csrf_token added by caller; allow_guest dev path also uses this)
		"session_user": user,
		"session_user_full_name": user_doc.full_name or user,
		"session_user_image": user_doc.user_image or "",

		# Frappe defaults
		"sysdefaults": {
			"default_company": frappe.defaults.get_user_default("Company"),
			"default_currency": frappe.defaults.get_user_default("Currency") or "PKR",
		},

		# Cashew-app config (live-updated via realtime D8)
		"cashew_settings": {
			"default_company": settings.company,
			"accent_color": settings.accent_color or "Indigo",
			"accent_color_custom": settings.accent_color_custom or "",
		},

		# c014: server-rendered theme_color so the <meta name="theme-color">
		# tag matches the user's accent on first paint (no Indigo flash
		# before ThemeController.init runs).
		"theme_color": resolve_theme_color(),

		# Server-default period for dashboard (current month start → today)
		"default_period_start": str(period_start),
		"default_period_end": str(today),

		# The FISCAL year, which is an ERPNext doctype and frequently is not the
		# calendar year — this site runs July to June. The client cannot derive
		# it, and guessing January would silently hand the reader six months of
		# the previous year under a "This Fiscal Year" label.
		"fiscal_year": _current_fiscal_year(today),

		# Sole boot-time perm flag — other writes checked per-action (D5.3)
		"can_write_settings": frappe.has_permission(
			"Cashew Settings", ptype="write", throw=False
		),

		# Socket.IO (D8). Port comes from common_site_config.json; default 9000.
		"socketio_port": frappe.conf.socketio_port or 9000,
		"realtime_token": frappe.sessions.get_csrf_token(),
	})
