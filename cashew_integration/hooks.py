app_name = "cashew_integration"
app_title = "Cashew Integration"
app_publisher = "Cashew"
app_description = "Integration with Cashew for importing CSV files."
app_email = "ra9496300@gmail.com"
app_license = "mit"
app_logo_url = "/assets/cashew_integration/images/cashew-integration-logo.svg"
app_home = "/app/cashew-integration"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "cashew_integration",
		"logo": "/assets/cashew_integration/images/cashew-integration-logo.svg",
		"title": "Cashew Integration",
		"route": "/app/cashew-integration",
	}
]


# --- Cashew SPA (f010) --------------------------------------------------
# website_route_rules is appended by `bench add-spa` near end of file; do not
# duplicate the assignment here — Python's last-assignment-wins would shadow it.

app_icon_url = "/assets/cashew_integration/images/cashew-app-icon.svg"
app_icon_route = "/cashew"
app_icon_title = "Cashew"


# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/nexus_erp/css/nexus_erp.css"
# app_include_js = "/assets/nexus_erp/js/nexus_erp.js"

# include js, css files in header of web template
# web_include_css = "/assets/nexus_erp/css/nexus_erp.css"
# web_include_js = "/assets/nexus_erp/js/nexus_erp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "nexus_erp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}




# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "nexus_erp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "nexus_erp.utils.jinja_methods",
# 	"filters": "nexus_erp.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "cashew_integration.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "nexus_erp.uninstall.before_uninstall"
# after_uninstall = "nexus_erp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "nexus_erp.utils.before_app_install"
# after_app_install = "nexus_erp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "nexus_erp.utils.before_app_uninstall"
# after_app_uninstall = "nexus_erp.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "nexus_erp.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events



# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"nexus_erp.tasks.all"
# 	],
# 	"daily": [
# 		"nexus_erp.tasks.daily"
# 	],
# 	"hourly": [
# 		"nexus_erp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"nexus_erp.tasks.weekly"
# 	],
# 	"monthly": [
# 		"nexus_erp.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "nexus_erp.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "nexus_erp.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "nexus_erp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "nexus_erp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["nexus_erp.utils.before_request"]
# after_request = ["nexus_erp.utils.after_request"]

# Job Events
# ----------
# before_job = ["nexus_erp.utils.before_job"]
# after_job = ["nexus_erp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"nexus_erp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# Fixtures
# --------
fixtures = []


# PWA: /cashew/sw.js + /cashew/manifest.webmanifest take precedence over
# the SPA catch-all. SW needs to live inside the SPA scope; manifest is
# served dynamically so theme_color tracks Cashew Settings.accent_color.
website_route_rules = [
	{'from_route': '/cashew/sw.js', 'to_route': 'cashew_sw'},
	{'from_route': '/cashew/manifest.webmanifest', 'to_route': 'cashew_manifest'},
	{'from_route': '/cashew/<path:app_path>', 'to_route': 'cashew'},
]

page_renderer = ['cashew_integration.pwa.CashewPWAFile']