// Cashew Import Run — form client script
// Adds workflow buttons: Parse & Preview → Queue Run → live progress polling.

frappe.ui.form.on("Cashew Import Run", {

	refresh(frm) {
		// Always stop any existing timer first — refresh fires when the user
		// navigates between records, and a timer left over from the previous
		// record will keep polling and (worse) write its status to the new
		// frm.doc. Re-start only if the current record is in a polling state.
		_stop_progress_polling();
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

	// ── Ready to Import (arm) ────────────────────────────────────────────────────
	// Explicit Parsed -> Validated step. Validate is now a pure check that leaves
	// the run at Parsed (Option A decouple); arming is the deliberate commit and
	// refuses while any row is in error.
	_arm_import(frm) {
		frappe.confirm(
			__("Arm this import for posting? You still confirm at Queue Run."),
			() => {
				frm.call({
					method: "cashew_integration.api.arm_import",
					args:   { run_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Arming import…"),
					callback(r) {
						if (r.message) {
							frappe.show_alert({
								message: __(
									"Ready to import — {0} valid rows. Click Queue Run to post.",
									[r.message.rows_valid]
								),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			}
		);
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

	// Field Guide — "what does each row field mean?" help. Always available.
	// Content comes from the shared get_import_row_field_guide endpoint so the
	// Desk dialog and the SPA show identical definitions.
	frm.add_custom_button(__("Field Guide"), () => _show_field_guide());

	// Open in Row Explorer (f006 c007) — deep-link to the Vue page.
	// Visible whenever the run has rows, regardless of status (audit + edit).
	if (frm.doc.rows_total && frm.doc.rows_total > 0) {
		frm.add_custom_button(__("Open in Row Explorer"), () => {
			frappe.set_route("cashew-row-explorer", frm.doc.name);
		});
	}

	// Parse & Preview: available in Draft/Imported/Validated (re-parse)
	if (["Draft", "Parsed", "Validated"].includes(s)) {
		frm.add_custom_button(__("Parse & Preview"), () => {
			frm.trigger("_parse_and_preview");
		}).addClass("btn-primary");
	}

	// Validate Import: strict checks before queueing.
	// Visible on Parsed AND Validated so the user can re-validate after
	// editing rows / mappings without having to Parse again.
	if (["Parsed", "Validated"].includes(s)) {
		frm.add_custom_button(__("Validate Import"), () => {
			frm.trigger("_validate_import");
		}).addClass("btn-warning");
	}

	// Ready to Import: arm Parsed -> Validated. Explicit commit; Validate no
	// longer advances the run (Option A decouple). Primary CTA at Parsed.
	if (s === "Parsed") {
		frm.add_custom_button(__("Ready to Import"), () => {
			frm.trigger("_arm_import");
		}).addClass("btn-primary");
	}

	// Queue Run: only once armed (Validated)
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
		// Capture the polled run name at tick time. Frappe Desk reuses the
		// same `frm` object across navigations within a doctype, so by the
		// time the response returns the user may already be on a different
		// record. Using a stale snapshot to write `frm.doc.status` clobbers
		// the new record (e.g. flips a fresh Draft import to Reverted while
		// an older run is still reverting). Bail if the name moved.
		const polledName = frm.doc.name;
		frappe.call({
			method: "cashew_integration.api.get_run_progress",
			args:   { run_name: polledName },
			callback(r) {
				if (!r.message) return;
				if (!frm.doc || frm.doc.name !== polledName) return;
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

// ── Field Guide ──────────────────────────────────────────────────────────────
// Fetched once per session from the shared endpoint, then cached. The SPA calls
// the same cashew_integration.api.get_import_row_field_guide method.
let _field_guide_cache = null;

async function _show_field_guide() {
	if (!_field_guide_cache) {
		const r = await frappe.call({
			method: "cashew_integration.api.get_import_row_field_guide",
			freeze: true,
			freeze_message: __("Loading field guide…"),
		});
		_field_guide_cache = r.message || [];
	}

	const esc = frappe.utils.escape_html;
	const groups_html = _field_guide_cache.map((grp) => {
		const rows = grp.fields.map((f) => `
			<tr class="fg-row">
				<td class="fg-label" style="white-space:nowrap;vertical-align:top;padding:6px 12px 6px 0;font-weight:600;">
					${esc(f.label)}
					<div class="text-muted" style="font-weight:400;font-size:11px;">${esc(f.fieldname)}</div>
				</td>
				<td class="fg-def" style="vertical-align:top;padding:6px 0;">${esc(f.definition)}</td>
			</tr>`).join("");
		return `
			<div class="fg-group" style="margin-bottom:18px;">
				<h5 style="margin-bottom:2px;">${esc(grp.group)}</h5>
				${grp.intro ? `<div class="text-muted" style="font-size:12px;margin-bottom:8px;">${esc(grp.intro)}</div>` : ""}
				<table class="table table-sm" style="margin:0;"><tbody>${rows}</tbody></table>
			</div>`;
	}).join("");

	const d = new frappe.ui.Dialog({
		title: __("Import Row — Field Guide"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "guide" }],
	});
	d.fields_dict.guide.$wrapper.html(`
		<div style="margin-bottom:10px;">
			<input type="text" class="form-control fg-search" placeholder="${__("Filter fields…")}">
		</div>
		<div class="fg-body">${groups_html}</div>
	`);

	// Client-side filter across label, fieldname, and definition text.
	d.$wrapper.find(".fg-search").on("keyup", function () {
		const q = (this.value || "").toLowerCase();
		d.$wrapper.find(".fg-group").each(function () {
			const $grp = $(this);
			let any = false;
			$grp.find(".fg-row").each(function () {
				const match = $(this).text().toLowerCase().includes(q);
				$(this).toggle(match);
				if (match) any = true;
			});
			$grp.toggle(any);
		});
	});

	d.show();
}
