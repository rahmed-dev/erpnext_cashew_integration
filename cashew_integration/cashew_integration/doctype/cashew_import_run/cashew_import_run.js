// Cashew Import Run — form client script
// Adds workflow buttons: Parse & Preview → Queue Run → live progress polling.

frappe.ui.form.on("Cashew Import Run", {

	refresh(frm) {
		_update_buttons(frm);
		if (["Queued", "Processing", "Reverting"].includes(frm.doc.status)) {
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
					const parts = [];
					parts.push(`<b>${__("Result")}</b>`);
					parts.push(`<ul><li>${__("{0} rows passed validation.", [m.rows_valid])}</li></ul>`);
					if (fxLine) {
						parts.push(`<b>${__("Exchange Rates")}</b>`);
						parts.push(`<ul><li>${fxLine}</li></ul>`);
					}
					frappe.msgprint({
						title: __("Validation Passed"),
						message: parts.join(""),
						indicator: "green",
					});
				} else {
					const cfg    = m.run_config_errors || [];
					const fxErr  = m.fx_error_count || 0;
					const pairs  = fx.missing_pairs || [];
					const parts  = [];

					// ── Summary ───────────────────────────────────────────────
					parts.push(`<b>${__("Summary")}</b>`);
					parts.push("<ul>");
					parts.push(`<li>${__("{0} row(s) have errors.", [m.rows_failed || 0])}</li>`);
					if (fxErr)      parts.push(`<li>${__("{0} row(s) missing exchange rate.", [fxErr])}</li>`);
					if (cfg.length) parts.push(`<li>${__("{0} configuration issue(s).", [cfg.length])}</li>`);
					parts.push("</ul>");

					// ── Row error breakdown ───────────────────────────────────
					if (m.error_code_counts && Object.keys(m.error_code_counts).length) {
						parts.push(`<b>${__("Row Errors")}</b>`);
						parts.push("<ul>");
						Object.entries(m.error_code_counts).forEach(([code, count]) => {
							parts.push(`<li><code>${code}</code> — ${count} row(s)</li>`);
						});
						parts.push("</ul>");
					}

					// ── Config errors ─────────────────────────────────────────
					if (cfg.length) {
						parts.push(`<b>${__("Configuration Errors")}</b>`);
						parts.push("<ul>");
						cfg.forEach(e => parts.push(`<li>${e}</li>`));
						parts.push("</ul>");
					}

					// ── Missing FX records ────────────────────────────────────
					if (pairs.length) {
						parts.push(`<b>${__("Missing Currency Exchange Records")}</b>`);
						parts.push("<ul>");
						pairs.forEach(p => parts.push(`<li>${p.from} → ${p.to} &nbsp;<i>(${p.date})</i></li>`));
						parts.push("</ul>");
						parts.push(`<i>${__("Create these under ERPNext → Accounting → Currency Exchange, then click Validate Import again.")}</i>`);
					}

					// ── FX summary ────────────────────────────────────────────
					if (fxLine) {
						parts.push(`<br><b>${__("Exchange Rates")}</b>`);
						parts.push(`<ul><li>${fxLine}</li></ul>`);
					}

					frappe.msgprint({
						title: __("Validation Issues"),
						message: parts.join(""),
						indicator: "orange",
					});
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
	if (["Draft", "Parsed", "Validated"].includes(s)) {
		frm.add_custom_button(__("Parse & Preview"), () => {
			frm.trigger("_parse_and_preview");
		}).addClass("btn-primary");
	}

	// Validate Import: strict checks before queueing
	if (s === "Parsed") {
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

	// Revert Run: cancel all posted ERP docs for completed/failed/cancelled runs
	if (["Completed", "Failed", "Cancelled", "Revert-Failed"].includes(s)) {
		frm.add_custom_button(__("Revert Run"), () => {
			frappe.confirm(
				__("This will cancel all posted Sales Invoices, Purchase Invoices, and Journal Entries for this run. Continue?"),
				() => {
					frm.call({
						method: "cashew_integration.api.revert_run",
						args: { run_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Submitting revert request…"),
						callback(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Revert started — ERP documents are being cancelled."),
									indicator: "orange",
								});
								frm.reload_doc();
								_start_progress_polling(frm);
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

				// Update counters and status in-place without marking form dirty.
				// frm.set_value() triggers dirty; mutate doc + refresh_field() instead.
				const fields = {
					status:       p.status,
					rows_posted:  p.rows_posted,
					rows_failed:  p.rows_failed,
					rows_skipped: p.rows_skipped,
					started_on:   p.started_on  || frm.doc.started_on,
					finished_on:  p.finished_on || frm.doc.finished_on,
				};
				Object.entries(fields).forEach(([f, v]) => {
					frm.doc[f] = v;
					frm.refresh_field(f);
				});

				if (!["Queued", "Processing", "Reverting"].includes(p.status)) {
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
