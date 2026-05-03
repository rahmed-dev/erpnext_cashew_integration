// Copyright (c) 2026, riz
// MIT License (MIT)

// Dynamic link_filters on default_account based on row category_type.
// Server-side validate is the safety net (see cashew_category_mapping.py).

const FILTERS_BY_TYPE = {
	"Income":   [["Account", "is_group", "=", 0], ["Account", "root_type", "=", "Income"]],
	"Expense":  [["Account", "is_group", "=", 0], ["Account", "root_type", "=", "Expense"]],
	"Loan Out": [["Account", "is_group", "=", 0], ["Account", "root_type", "=", "Asset"],     ["Account", "account_type", "=", "Receivable"]],
	"Loan In":  [["Account", "is_group", "=", 0], ["Account", "root_type", "=", "Liability"], ["Account", "account_type", "=", "Payable"]],
};

const DEFAULT_FILTERS = [["Account", "is_group", "=", 0]];

function _filters_for(category_type) {
	return FILTERS_BY_TYPE[category_type] || DEFAULT_FILTERS;
}

frappe.ui.form.on("Cashew Category Mapping", {
	refresh(frm) {
		frm.set_query("default_account", "cashew_category_mapping", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn] || {};
			return { filters: _filters_for(row.category_type) };
		});
	},
	category_type(frm, cdt, cdn) {
		// Clear stale account on type change — user picks a fresh one.
		const row = locals[cdt][cdn];
		if (row && row.default_account) {
			frappe.model.set_value(cdt, cdn, "default_account", null);
		}
	},
});
