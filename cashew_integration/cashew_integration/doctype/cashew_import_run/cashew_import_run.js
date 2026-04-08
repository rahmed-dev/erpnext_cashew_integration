// Cashew Import Run — form client script
// Adds workflow buttons: Parse & Preview → Queue Run → live progress polling.

frappe.ui.form.on("Cashew Import Run", {

	refresh(frm) {
		_update_buttons(frm);
		if (["Queued", "Processing"].includes(frm.doc.status)) {
			_start_progress_polling(frm);
		}
	},

	// ── Parse & Preview ────────────────────────────────────────────────────────

	async _parse_and_preview(frm) {
		if (!frm.doc.source_file) {
			frappe.msgprint(__("Please attach a Cashew CSV file before parsing."));
			return;
		}
		if (!frm.doc.company) {
			frappe.msgprint(__("Please select a Company before parsing."));
			return;
		}
		if (!(await _save_if_dirty(frm))) return;
		frm.call({
			method: "cashew_integration.api.parse_and_preview",
			args:   { run_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Parsing CSV…"),
			callback(r) {
				if (r.message) {
					const m = r.message;
					frappe.show_alert({
						message: __(
							"Parsed {0} rows — {1} valid, {2} errors.",
							[m.rows_total, m.rows_valid, m.rows_failed]
						),
						indicator: m.rows_failed > 0 ? "orange" : "green",
					});
					frm.reload_doc();
				}
			},
		});
	},

	// ── Queue Run ──────────────────────────────────────────────────────────────

	_validate_import(frm) {
		frm.call({
			method: "cashew_integration.api.validate_import",
			args: { run_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Fetching exchange rates & validating…"),
			callback(r) {
				if (!r.message) return;
				const m = r.message;
				const fx = m.fx_summary || {};
				const fxLine = fx.fetched != null
					? __("Exchange rates: {0} fetched, {1} already set, {2} not found.", [fx.fetched, fx.already_set, fx.failed])
					: "";

				if (m.status === "validated") {
					frappe.show_alert({
						message: __("Validation passed — {0} valid rows.", [m.rows_valid]),
						indicator: "green",
					});
					if (fxLine) {
						frappe.show_alert({ message: fxLine, indicator: "blue" });
					}
				} else {
					const cfg = (m.run_config_errors || []).length;
					const fxErr = m.fx_error_count || 0;
					let msg = __("Validation issues — {0} row errors, {1} FX missing, {2} config issues.", [m.rows_failed || 0, fxErr, cfg]);
					if (fxLine) msg += "<br>" + fxLine;
					frappe.show_alert({ message: msg, indicator: "orange" });

					if (m.error_code_counts && Object.keys(m.error_code_counts).length) {
						const lines = Object.entries(m.error_code_counts)
							.map(([code, count]) => `<b>${code}</b>: ${count}`)
							.join("<br>");
						const cfgLines = (m.run_config_errors || []).map(e => `• ${e}`).join("<br>");

						// Show which exact Currency Exchange records are missing
						const pairs = (fx.missing_pairs || []);
						const pairsHtml = pairs.length
							? "<br><br><b>Missing Currency Exchange records:</b><br>" +
							  pairs.map(p => `• ${p.from} → ${p.to} on ${p.date}`).join("<br>") +
							  `<br><br><i>Create these in <b>ERPNext → Accounting → Currency Exchange</b>, then click Validate Import again.</i>`
							: "";

						frappe.msgprint({
							title: __("Validation Error Breakdown"),
							message: lines
								+ (cfgLines ? "<br><br><b>Config errors:</b><br>" + cfgLines : "")
								+ pairsHtml,
							indicator: "orange",
						});
					}
				}
				frm.reload_doc();
			},
		});
	},

	_queue_run(frm) {
		frappe.confirm(
			__("Queue this import run? Rows will be posted to ERPNext."),
			async () => {
				if (!(await _save_if_dirty(frm))) return;
				frm.call({
					method: "cashew_integration.api.queue_run",
					args:   { run_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Queuing run…"),
					callback(r) {
						if (r.message) {
							frappe.show_alert({
								message: __(
									"Queued — {0} valid rows to post.",
									[r.message.rows_valid]
								),
								indicator: "blue",
							});
							frm.reload_doc();
						}
					},
				});
			}
		);
	},
});


// ── helpers ───────────────────────────────────────────────────────────────────

function _update_buttons(frm) {
	const s = frm.doc.status;

	// Parse & Preview: available in Draft/Imported/Validated (re-parse)
	if (["Draft", "Imported", "Validated"].includes(s)) {
		frm.add_custom_button(__("Parse & Preview"), () => {
			frm.trigger("_parse_and_preview");
		}).addClass("btn-primary");
	}

	// Validate Import: strict checks before queueing
	if (s === "Imported") {
		frm.add_custom_button(__("Validate Import"), () => {
			frm.trigger("_validate_import");
		}).addClass("btn-warning");
	}

	// Queue Run: only once Validated
	if (s === "Validated") {
		frm.add_custom_button(__("Queue Run"), () => {
			frm.trigger("_queue_run");
		}).addClass("btn-success");
	}

	// Cancel Import: available while queued/processing
	if (["Queued", "Processing"].includes(s)) {
		frm.add_custom_button(__("Cancel Import"), () => {
			frappe.confirm(
				__("Cancel this import run? Any remaining rows will stop processing."),
				() => {
					frm.call({
						method: "cashew_integration.api.cancel_run",
						args: { run_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Cancelling run..."),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Import run cancelled."),
									indicator: "orange",
								});
								frm.reload_doc();
							}
						},
					});
				}
			);
		}).addClass("btn-danger");
	}
}


let _poll_timer = null;

function _start_progress_polling(frm) {
	// Guard: don't stack multiple timers
	if (_poll_timer) return;

	_poll_timer = setInterval(() => {
		if (!frm.doc || !frm.doc.name) {
			_stop_progress_polling();
			return;
		}
		frappe.call({
			method: "cashew_integration.api.get_run_progress",
			args:   { run_name: frm.doc.name },
			callback(r) {
				if (!r.message) return;
				const p = r.message;

				// Update the counter fields in-place without a full reload
				frm.set_value("rows_posted",  p.rows_posted);
				frm.set_value("rows_failed",  p.rows_failed);
				frm.set_value("rows_skipped", p.rows_skipped);

				if (!["Queued", "Processing"].includes(p.status)) {
					_stop_progress_polling();
					frm.reload_doc();
				}
			},
		});
	}, 3000);
}

function _stop_progress_polling() {
	if (_poll_timer) {
		clearInterval(_poll_timer);
		_poll_timer = null;
	}
}

async function _save_if_dirty(frm) {
	if (!frm.is_dirty()) return true;
	try {
		await frm.save();
		return true;
	} catch (e) {
		frappe.msgprint(__("Please fix validation errors and save the form before continuing."));
		return false;
	}
}
