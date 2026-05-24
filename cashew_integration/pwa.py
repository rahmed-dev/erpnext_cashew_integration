"""PWA service-worker + manifest renderer for the Cashew SPA (f010 c014).

The SPA is mounted at /cashew/ via a catch-all website_route_rule that maps
every /cashew/<path:app_path> to cashew.html. For the SPA to be installable
as a PWA, the service worker MUST control start_url=/cashew/. That requires
the SW response to be served from inside /cashew/ AND carry the header
Service-Worker-Allowed: /cashew/ (because the SW file physically lives in
the app's public/frontend/ build output, not at the SPA root).

The web manifest is also served from /cashew/ so it can be generated
dynamically from Cashew Settings — theme_color tracks the user-chosen
accent color (preset or custom hex). Installed PWA reflects the accent
chosen at install time; live browser-chrome tinting is updated in
ThemeController via the <meta name="theme-color"> tag.
"""

import json
import os
import re

from werkzeug.wrappers import Response

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

# Mirror of frontend/src/theme.js PRESET_TABLE (primary shade only).
# Keep in sync with that file — Tailwind 3.x palette per arch D14.b.
ACCENT_PRESETS = {
	"Indigo": "#4f46e5",
	"Teal": "#0d9488",
	"Burnt Orange": "#ea580c",
	"Monochrome": "#1f2937",
	"Cyan": "#0891b2",
}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_THEME = "#4f46e5"
ASSET_BASE = "/assets/cashew_integration/frontend"


def resolve_theme_color() -> str:
	"""Return the accent primary hex from Cashew Settings (or default)."""
	try:
		settings = frappe.get_cached_doc("Cashew Settings", "Cashew Settings")
	except Exception:
		return DEFAULT_THEME

	accent = (settings.accent_color or "Indigo").strip()
	if accent == "Custom":
		custom = (settings.accent_color_custom or "").strip()
		if HEX_RE.match(custom):
			return custom
		return DEFAULT_THEME
	return ACCENT_PRESETS.get(accent, DEFAULT_THEME)


def build_manifest() -> dict:
	return {
		"id": "/cashew/",
		"name": "Cashew",
		"short_name": "Cashew",
		"description": "Cashew — bank-statement import, validation, posting (ERPNext)",
		"start_url": "/cashew/",
		"scope": "/cashew/",
		"display": "standalone",
		"orientation": "any",
		"lang": "en",
		"background_color": "#ffffff",
		"theme_color": resolve_theme_color(),
		"icons": [
			{"src": f"{ASSET_BASE}/pwa-64x64.png", "sizes": "64x64", "type": "image/png"},
			{"src": f"{ASSET_BASE}/pwa-192x192.png", "sizes": "192x192", "type": "image/png"},
			{"src": f"{ASSET_BASE}/pwa-512x512.png", "sizes": "512x512", "type": "image/png"},
			{
				"src": f"{ASSET_BASE}/maskable-icon-512x512.png",
				"sizes": "512x512",
				"type": "image/png",
				"purpose": "maskable",
			},
		],
	}


class CashewPWAFile(BaseRenderer):
	"""Serve PWA service worker + web manifest under the /cashew/ scope."""

	SW_PATH = "cashew_sw"
	MANIFEST_PATH = "cashew_manifest"

	def can_render(self):
		return self.path in (self.SW_PATH, self.MANIFEST_PATH)

	def render(self):
		if self.path == self.MANIFEST_PATH:
			return self._render_manifest()
		return self._render_sw()

	def _render_sw(self):
		file_path = os.path.join(
			frappe.get_app_path("cashew_integration"), "public", "frontend", "sw.js"
		)
		if not os.path.exists(file_path):
			return Response(
				"// cashew PWA asset not built yet - run `bench build --app cashew_integration`".encode("utf-8"),
				status=404,
				mimetype="text/plain",
			)
		with open(file_path, "rb") as fp:
			content = fp.read()
		response = Response(content, mimetype="application/javascript; charset=utf-8")
		response.headers["Cache-Control"] = "no-cache, must-revalidate"
		response.headers["Service-Worker-Allowed"] = "/cashew/"
		return response

	def _render_manifest(self):
		body = json.dumps(build_manifest(), separators=(",", ":")).encode("utf-8")
		response = Response(body, mimetype="application/manifest+json")
		# Cache briefly so install/refresh picks up Settings changes quickly.
		response.headers["Cache-Control"] = "no-cache, must-revalidate"
		return response
