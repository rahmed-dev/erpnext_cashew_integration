// f006 c006 — Cashew Row Explorer page controller.
// Lazy-loads the Vue bundle and mounts it into the page wrapper.

frappe.pages["cashew-row-explorer"].on_page_load = function (wrapper) {
	const route = frappe.get_route();
	const run_name = route[1] || frappe.utils.get_query_string(window.location.href).run;

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: run_name
			? __("Cashew Row Explorer — {0}", [run_name])
			: __("Cashew Row Explorer"),
		single_column: true,
	});

	if (!run_name) {
		$(page.body).html(
			`<div class="text-muted" style="padding:2rem;">${__(
				"No run name in URL. Open this page from a Cashew Import Run."
			)}</div>`
		);
		return;
	}

	// Bundle name (no path) — Frappe resolves via the asset manifest to the
	// hashed dist URL produced by `bench build`. Pointing at the raw source
	// path under /assets/<app>/js/ would serve the un-transformed ES-module
	// file and fail with "Cannot use import statement outside a module".
	frappe.require("cashew_row_explorer.bundle.js", () => {
		if (typeof window.cashew_mount_row_explorer !== "function") {
			$(page.body).html(
				`<div class="text-danger" style="padding:2rem;">${__(
					"Failed to load Row Explorer bundle. Run 'bench build --app cashew_integration' and retry."
				)}</div>`
			);
			return;
		}
		window.cashew_mount_row_explorer(page.body[0], { run_name, page });
	});
};
