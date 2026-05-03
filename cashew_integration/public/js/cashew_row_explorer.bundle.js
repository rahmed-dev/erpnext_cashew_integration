/* f006 c006 — Cashew Row Explorer (Vue 3 bundle).
 *
 * Single-file bundle: Vue components defined inline as objects with template
 * strings. No SFC loader required — Frappe's esbuild pipeline picks this up
 * automatically (any *.bundle.js under public/js).
 *
 * Mount surface:
 *   window.cashew_mount_row_explorer(el, { run_name, page })
 */

// `import from "vue"` resolves to the runtime-only build in Frappe v15
// (vue.runtime.esm-bundler.js — no template compiler). Templates given as
// JS strings would silently render to nothing. Use the bundler build that
// includes the compiler so our string templates work at runtime.
import { createApp, ref, reactive, computed, h, onMounted, watch } from "vue/dist/vue.esm-bundler.js";

// ── Column presets ────────────────────────────────────────────────────────────

// row_idx is rendered as the leading "Sr" column outside the preset list, so
// presets only declare the columns that follow Sr / Status. Keeping
// validation_status out — the standalone StatusPill column already shows it.
const PRESETS = {
	compact: {
		label: "Compact",
		columns: ["txn_date", "raw_amount", "txn_type", "category", "sub_category"],
	},
	resolution: {
		label: "Resolution",
		columns: [
			"txn_type", "category", "sub_category",
			"resolved_route", "resolved_account", "resolved_erp_account",
			"resolved_party_type", "resolved_party",
		],
	},
	validation: {
		label: "Validation",
		columns: [
			"txn_date", "raw_amount", "txn_type",
			"validation_error_code", "validation_error_message",
		],
	},
	posted: {
		label: "Posted",
		columns: [
			"txn_date", "raw_amount", "txn_type",
			"posted_doctype", "posted_docname", "posted_gl_date", "revert_status",
		],
	},
	loans_and_parties: {
		label: "Loans & Parties",
		columns: [
			"txn_date", "raw_amount", "txn_type",
			"category", "sub_category", "title", "note",
			"resolved_party_type", "resolved_party",
		],
	},
};

const COLUMN_LABELS = {
	row_idx: "Sr",
	txn_date: "Date",
	raw_amount: "Amount",
	source_currency: "Cur",
	txn_type: "Type",
	category: "Category",
	sub_category: "Sub",
	title: "Title",
	note: "Note",
	raw_account: "Source Acct",
	resolved_route: "Route",
	resolved_account: "Posting Account",
	resolved_erp_account: "Cash Account",
	resolved_external_account: "Ext Account",
	resolved_party_type: "Party Type",
	resolved_party: "Party",
	validation_status: "Status",
	validation_error_code: "Error Code",
	validation_error_message: "Message",
	posted_doctype: "Posted DocType",
	posted_docname: "Posted Doc",
	posted_gl_date: "GL Date",
	revert_status: "Revert",
};

const PARTY_REQUIRED_CODES = new Set(["LOAN_PARTY_MISSING", "PARTY_MISSING"]);

// Determine the party_type a row expects (from txn_type + requires_party).
function expectedPartyType(row) {
	if (row.txn_type === "Loan Receivable") return "Customer";
	if (row.txn_type === "Loan Payable") return "Supplier";
	if (row.requires_party && row.txn_type === "Income") return "Customer";
	if (row.requires_party && row.txn_type === "Expense") return "Supplier";
	return null;
}

// Render the status badge string + colour class for a row.
function rowStatus(row) {
	if (row.posted_docname) return { label: "Posted", cls: "blue" };
	if (row.revert_status === "Reverted") return { label: "Reverted", cls: "amber" };
	if (row.validation_status === "Error") return { label: "Error", cls: "red" };
	if (row.validation_status === "Skipped") return { label: "Skipped", cls: "gray" };
	if (row.validation_status === "Valid") return { label: "Valid", cls: "green" };
	return { label: "Pending", cls: "gray" };
}

// Mirror the rich Validate Import dialog rendered by the Cashew Import Run
// form so users get the same summary / error / FX breakdown from the explorer.
function renderValidateImportResult(m) {
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
		return;
	}

	const cfg = m.run_config_errors || [];
	const fxErr = m.fx_error_count || 0;
	const pairs = (m.fx_summary && m.fx_summary.missing_pairs) || [];
	const parts = [];

	parts.push(`<b>${__("Summary")}</b>`);
	parts.push("<ul>");
	parts.push(`<li>${__("{0} row(s) have errors.", [m.rows_failed || 0])}</li>`);
	if (fxErr) parts.push(`<li>${__("{0} row(s) missing exchange rate.", [fxErr])}</li>`);
	if (cfg.length) parts.push(`<li>${__("{0} configuration issue(s).", [cfg.length])}</li>`);
	parts.push("</ul>");

	if (m.error_code_counts && Object.keys(m.error_code_counts).length) {
		parts.push(`<b>${__("Row Errors")}</b>`);
		parts.push("<ul>");
		Object.entries(m.error_code_counts).forEach(([code, count]) => {
			parts.push(`<li><code>${code}</code> — ${count} row(s)</li>`);
		});
		parts.push("</ul>");
	}
	if (cfg.length) {
		parts.push(`<b>${__("Configuration Errors")}</b>`);
		parts.push("<ul>");
		cfg.forEach(e => parts.push(`<li>${e}</li>`));
		parts.push("</ul>");
	}
	if (pairs.length) {
		parts.push(`<b>${__("Missing Currency Exchange Records")}</b>`);
		parts.push("<ul>");
		pairs.forEach(p => parts.push(`<li>${p.from} → ${p.to} &nbsp;<i>(${p.date})</i></li>`));
		parts.push("</ul>");
		parts.push(`<i>${__("Create these under ERPNext → Accounting → Currency Exchange, then click Validate Import again.")}</i>`);
	}
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

// ── Status pill component ─────────────────────────────────────────────────────

const StatusPill = {
	props: ["row"],
	setup(props) {
		const s = computed(() => rowStatus(props.row));
		return { s };
	},
	template: `<span :class="['cre-pill', 'cre-pill-' + s.cls]">{{ s.label }}</span>`,
};

// ── Frappe Link control wrapper for party picker ──────────────────────────────

const PartyPicker = {
	props: { partyType: { type: String, required: true }, modelValue: String },
	emits: ["update:modelValue"],
	setup(props, { emit }) {
		const wrapperRef = ref(null);
		let control = null;

		// Frappe's Link control fires its committed value through
		// `df.onchange` after Awesomplete picks complete. Native `change` on
		// $input alone misses autocomplete picks, so we hook both onchange
		// and the awesomplete-selectcomplete event for belt-and-braces.
		const buildControl = () => {
			if (!wrapperRef.value) return;
			$(wrapperRef.value).empty();
			control = frappe.ui.form.make_control({
				parent: wrapperRef.value,
				df: {
					fieldtype: "Link",
					fieldname: "party",
					options: props.partyType,
					placeholder: __("Pick {0}…", [props.partyType]),
					label: "",
					onchange() {
						emit("update:modelValue", this.value || "");
					},
				},
				render_input: true,
			});
			control.set_value(props.modelValue || "");
			control.$input.on(
				"change awesomplete-selectcomplete blur",
				() => emit("update:modelValue", control.get_value() || "")
			);
		};

		onMounted(buildControl);
		watch(() => props.partyType, buildControl);
		watch(() => props.modelValue, (v) => {
			if (control && control.get_value() !== (v || "")) {
				control.set_value(v || "");
			}
		});

		return { wrapperRef };
	},
	template: `<div ref="wrapperRef" class="cre-party-picker"></div>`,
};

// ── Fix modal — error-code dispatcher ─────────────────────────────────────────

const FixModal = {
	props: ["row", "runName", "mutationAllowed"],
	emits: ["close", "row-updated"],
	setup(props, { emit }) {
		const partyType = ref(expectedPartyType(props.row) || "Customer");
		const party = ref(props.row.resolved_party || "");
		const saving = ref(false);
		const errorCode = computed(() => props.row.validation_error_code);
		const isParty = computed(() => PARTY_REQUIRED_CODES.has(errorCode.value));
		const message = computed(() => props.row.validation_error_message || "");

		const settingsLink = "/app/cashew-settings";

		const onSave = async () => {
			if (!isParty.value || !party.value) return;
			saving.value = true;
			try {
				const r = await frappe.call({
					method: "cashew_integration.api.row_explorer_set_party",
					args: {
						run_name: props.runName,
						row_indices: [props.row.row_idx],
						party_type: partyType.value,
						party: party.value,
					},
				});
				if (r.message && r.message.updated && r.message.updated.length) {
					emit("row-updated", r.message.updated[0]);
				}
				emit("close");
			} finally {
				saving.value = false;
			}
		};

		return {
			partyType, party, saving, errorCode, isParty, message,
			settingsLink, onSave,
		};
	},
	components: { PartyPicker },
	template: `
	<div class="cre-modal-backdrop" @click.self="$emit('close')">
		<div class="cre-modal">
			<div class="cre-modal-header">
				<strong>{{ __('Fix row {0}', [row.row_idx]) }}</strong>
				<span class="cre-modal-code">{{ errorCode || '—' }}</span>
				<button class="btn btn-xs btn-default" @click="$emit('close')">&times;</button>
			</div>
			<div class="cre-modal-body">
				<p class="text-muted" style="white-space:pre-wrap">{{ message }}</p>
				<template v-if="isParty">
					<label>{{ __('Party Type') }}</label>
					<select class="form-control" v-model="partyType" :disabled="!mutationAllowed">
						<option value="Customer">Customer</option>
						<option value="Supplier">Supplier</option>
					</select>
					<label style="margin-top:0.5rem">{{ __('Party') }}</label>
					<PartyPicker :party-type="partyType" v-model="party" />
				</template>
				<template v-else-if="errorCode === 'CATEGORY_NOT_MAPPED' || errorCode === 'CATEGORY_ACCOUNT_CLASS_MISMATCH'">
					<a class="btn btn-default btn-sm" :href="settingsLink" target="_blank">
						{{ __('Open Cashew Settings') }}
					</a>
				</template>
				<template v-else-if="errorCode === 'CASHEW_ACCOUNT_NOT_MAPPED' || errorCode === 'EXTERNAL_ACCOUNT_NOT_MAPPED'">
					<a class="btn btn-default btn-sm" :href="settingsLink" target="_blank">
						{{ __('Open Cashew Settings — Account Mapping') }}
					</a>
				</template>
				<template v-else>
					<p class="text-muted">{{ __('Fix the underlying mapping or rule, then click Re-validate.') }}</p>
				</template>
			</div>
			<div class="cre-modal-footer">
				<button class="btn btn-default btn-sm" @click="$emit('close')">{{ __('Close') }}</button>
				<button v-if="isParty"
					class="btn btn-primary btn-sm"
					@click="onSave"
					:disabled="!mutationAllowed || !party || saving">
					{{ saving ? __('Saving…') : __('Save Party') }}
				</button>
			</div>
		</div>
	</div>`,
};

// ── Bulk party modal ──────────────────────────────────────────────────────────

const BulkPartyModal = {
	props: ["runName", "selectedRows", "mutationAllowed"],
	emits: ["close", "rows-updated"],
	setup(props, { emit }) {
		// Try to derive a uniform partyType from the selection (loans force a side).
		const initialType = (() => {
			const types = new Set(
				props.selectedRows.map(expectedPartyType).filter(Boolean)
			);
			if (types.size === 1) return [...types][0];
			return "Customer";
		})();
		const partyType = ref(initialType);
		const party = ref("");
		const saving = ref(false);

		const onSave = async () => {
			if (!party.value) return;
			saving.value = true;
			try {
				const r = await frappe.call({
					method: "cashew_integration.api.row_explorer_set_party",
					args: {
						run_name: props.runName,
						row_indices: props.selectedRows.map((r) => r.row_idx),
						party_type: partyType.value,
						party: party.value,
					},
				});
				emit("rows-updated", (r.message && r.message.updated) || []);
				emit("close");
			} finally {
				saving.value = false;
			}
		};

		return { partyType, party, saving, onSave };
	},
	components: { PartyPicker },
	template: `
	<div class="cre-modal-backdrop" @click.self="$emit('close')">
		<div class="cre-modal">
			<div class="cre-modal-header">
				<strong>{{ __('Set party on {0} rows', [selectedRows.length]) }}</strong>
				<button class="btn btn-xs btn-default" @click="$emit('close')">&times;</button>
			</div>
			<div class="cre-modal-body">
				<label>{{ __('Party Type') }}</label>
				<select class="form-control" v-model="partyType" :disabled="!mutationAllowed">
					<option value="Customer">Customer</option>
					<option value="Supplier">Supplier</option>
				</select>
				<label style="margin-top:0.5rem">{{ __('Party') }}</label>
				<PartyPicker :party-type="partyType" v-model="party" />
				<p class="text-muted" style="margin-top:0.5rem">
					{{ __('Posted and Reverted rows in the selection are skipped.') }}
				</p>
			</div>
			<div class="cre-modal-footer">
				<button class="btn btn-default btn-sm" @click="$emit('close')">{{ __('Cancel') }}</button>
				<button class="btn btn-primary btn-sm"
					@click="onSave"
					:disabled="!mutationAllowed || !party || saving">
					{{ saving ? __('Saving…') : __('Set Party') }}
				</button>
			</div>
		</div>
	</div>`,
};

// ── Root app ──────────────────────────────────────────────────────────────────

const App = {
	props: ["runName"],
	components: { StatusPill, FixModal, BulkPartyModal },
	setup(props) {
		const data = reactive({
			loaded: false,
			runName: props.runName,
			status: "",
			company: "",
			company_currency: "",
			counters: { total: 0, valid: 0, posted: 0, failed: 0, skipped: 0 },
			mutationAllowed: false,
			rows: [],
			enums: { txn_type: [], validation_status: [] },
		});
		const presetKey = ref("compact");
		const filterText = ref("");
		const filterStatus = ref("");
		const filterTxnType = ref("");
		const selected = ref(new Set());
		const fixModalRow = ref(null);
		const bulkModalOpen = ref(false);
		const loading = ref(false);

		const presetCols = computed(() => PRESETS[presetKey.value].columns);

		// Fields the free-text filter scans. Kept in sync with the haystack
		// in filteredRows() so we can highlight which columns produced the
		// match when they aren't visible in the active preset.
		const SEARCHABLE_COLS = [
			"category", "sub_category", "title", "note",
			"txn_type", "resolved_route",
			"resolved_party", "resolved_party_type",
			"resolved_account", "resolved_erp_account", "resolved_external_account",
			"validation_error_code", "validation_error_message",
			"raw_account", "posted_doctype", "posted_docname",
		];

		// Inline party-edit state — one row at a time. {rowIdx, partyType, party}.
		const editingParty = ref({ rowIdx: null, partyType: null, party: "" });
		const startPartyEdit = (row) => {
			if (!data.mutationAllowed) return;
			if (row.posted_docname || row.revert_status === "Reverted") return;
			editingParty.value = {
				rowIdx: row.row_idx,
				partyType: row.resolved_party_type || expectedPartyType(row) || "Customer",
				party: row.resolved_party || "",
			};
		};
		const cancelPartyEdit = () => {
			editingParty.value = { rowIdx: null, partyType: null, party: "" };
		};
		const savePartyEdit = async (row) => {
			const e = editingParty.value;
			if (e.rowIdx !== row.row_idx || !e.party) return;
			loading.value = true;
			try {
				const r = await frappe.call({
					method: "cashew_integration.api.row_explorer_set_party",
					args: {
						run_name: data.runName,
						row_indices: [row.row_idx],
						party_type: e.partyType,
						party: e.party,
					},
				});
				if (r.message && r.message.updated) patchRows(r.message.updated);
				cancelPartyEdit();
			} finally {
				loading.value = false;
			}
		};

		const filteredRows = computed(() => {
			// Multi-word AND search: every whitespace-separated term must match
			// somewhere in the haystack. Wider field set so party names + ERP
			// account labels + posted-doc names are all reachable.
			const needles = filterText.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
			const status = filterStatus.value;
			const txn = filterTxnType.value;
			return data.rows.filter((r) => {
				if (status === "Posted" && !r.posted_docname) return false;
				if (status === "Reverted" && r.revert_status !== "Reverted") return false;
				if (
					status &&
					!["Posted", "Reverted"].includes(status) &&
					(r.validation_status || "") !== status
				)
					return false;
				if (txn && r.txn_type !== txn) return false;
				if (!needles.length) return true;
				const hay = [
					r.category, r.sub_category, r.title, r.note,
					r.txn_type, r.resolved_route,
					r.resolved_party, r.resolved_party_type,
					r.resolved_account, r.resolved_erp_account, r.resolved_external_account,
					r.validation_error_code, r.validation_error_message,
					r.raw_account, r.posted_doctype, r.posted_docname,
				]
					.filter(Boolean)
					.join(" ")
					.toLowerCase();
				return needles.every((n) => hay.includes(n));
			});
		});

		// Columns that actually produced a free-text match across the filtered
		// rows. Used to extend the visible columns when search is active so
		// the user can see WHY a row matched (otherwise hits in hidden fields
		// like resolved_party look like phantom matches).
		const matchedCols = computed(() => {
			const needles = filterText.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
			if (!needles.length) return [];
			const hit = new Set();
			for (const col of SEARCHABLE_COLS) {
				for (const r of filteredRows.value) {
					const v = (r[col] == null ? "" : String(r[col])).toLowerCase();
					if (v && needles.some((n) => v.includes(n))) {
						hit.add(col);
						break;
					}
				}
			}
			return [...hit];
		});

		const effectivePresetCols = computed(() => {
			const base = presetCols.value;
			const extra = matchedCols.value.filter((c) => !base.includes(c));
			return extra.length ? [...base, ...extra] : base;
		});

		const allFilteredSelected = computed(() => {
			const idxs = filteredRows.value.map((r) => r.row_idx);
			return idxs.length > 0 && idxs.every((i) => selected.value.has(i));
		});

		const selectedRows = computed(() =>
			data.rows.filter((r) => selected.value.has(r.row_idx))
		);

		const load = async () => {
			loading.value = true;
			try {
				const r = await frappe.call({
					method: "cashew_integration.api.row_explorer_load",
					args: { run_name: data.runName },
				});
				const m = r.message;
				data.status = m.status;
				data.company = m.company;
				data.company_currency = m.company_currency;
				data.counters = {
					total: m.rows_total, valid: m.rows_valid, posted: m.rows_posted,
					failed: m.rows_failed, skipped: m.rows_skipped,
				};
				data.mutationAllowed = m.mutation_allowed;
				data.rows = m.rows;
				data.enums = m.enums || data.enums;
				data.loaded = true;
			} finally {
				loading.value = false;
			}
		};

		// Per-row / selection-scoped revalidation — used by callers that want
		// to refresh just a subset (no rich dialog, just a toast).
		const revalidate = async (idxs = null) => {
			loading.value = true;
			try {
				const r = await frappe.call({
					method: "cashew_integration.api.row_explorer_revalidate",
					args: { run_name: data.runName, row_indices: idxs },
				});
				patchRows((r.message && r.message.revalidated) || []);
				frappe.show_alert({
					message: __("Re-validated {0} rows", [(r.message && r.message.revalidated || []).length]),
					indicator: "green",
				});
			} finally {
				loading.value = false;
			}
		};

		// Run-wide revalidation — calls the SAME validate_import endpoint the
		// Cashew Import Run form uses, then renders the same rich result dialog
		// so the explorer surfaces FX gaps, config issues, and per-code error
		// counts identically to the form button.
		const revalidateAll = async () => {
			loading.value = true;
			try {
				const r = await frappe.call({
					method: "cashew_integration.api.validate_import",
					args: { run_name: data.runName },
					freeze: true,
					freeze_message: __("Fetching exchange rates & validating…"),
				});
				if (r.message) renderValidateImportResult(r.message);
				await load();  // refresh rows + counters from DB
			} finally {
				loading.value = false;
			}
		};

		const patchRows = (updated) => {
			if (!updated || !updated.length) return;
			const byIdx = new Map(updated.map((u) => [u.row_idx, u]));
			data.rows = data.rows.map((r) => byIdx.get(r.row_idx) || r);
		};

		const toggleSelect = (idx, checked) => {
			const s = new Set(selected.value);
			if (checked) s.add(idx);
			else s.delete(idx);
			selected.value = s;
		};

		const toggleSelectAll = (checked) => {
			const s = new Set(selected.value);
			for (const r of filteredRows.value) {
				if (checked) s.add(r.row_idx);
				else s.delete(r.row_idx);
			}
			selected.value = s;
		};

		const openFixModal = (row) => {
			if (!row.validation_error_code) return;
			fixModalRow.value = row;
		};

		const onRowUpdated = (updatedRow) => patchRows([updatedRow]);
		const onRowsUpdated = (rows) => patchRows(rows);

		const formatCell = (row, col) => {
			const v = row[col];
			if (v === null || v === undefined) return "";
			if (col === "raw_amount" || col === "base_amount") {
				const cur = col === "raw_amount" ? row.source_currency : data.company_currency;
				return `${Number(v).toFixed(2)} ${cur || ""}`;
			}
			if (col === "validation_error_message" && typeof v === "string" && v.length > 80) {
				return v.slice(0, 80) + "…";
			}
			return String(v);
		};

		onMounted(load);

		return {
			data, presetKey, filterText, filterStatus, filterTxnType, selected,
			fixModalRow, bulkModalOpen, loading, presetCols, effectivePresetCols,
			filteredRows, allFilteredSelected, selectedRows,
			COLUMN_LABELS, PRESETS,
			rowStatus, formatCell, expectedPartyType,
			load, revalidate, revalidateAll, toggleSelect, toggleSelectAll,
			openFixModal, onRowUpdated, onRowsUpdated,
			editingParty, startPartyEdit, cancelPartyEdit, savePartyEdit,
		};
	},
	template: `
	<div class="cre-root">
		<div v-if="!data.loaded" class="cre-empty">{{ __('Loading…') }}</div>
		<template v-else>
			<div class="cre-toolbar">
				<input class="form-control input-sm cre-search"
					v-model="filterText"
					:placeholder="__('Search category / title / note / party / error…')" />
				<select class="form-control input-sm" v-model="filterStatus">
					<option value="">{{ __('All statuses') }}</option>
					<option value="Valid">Valid</option>
					<option value="Error">Error</option>
					<option value="Skipped">Skipped</option>
					<option value="Posted">Posted</option>
					<option value="Reverted">Reverted</option>
				</select>
				<select class="form-control input-sm" v-model="filterTxnType">
					<option value="">{{ __('All types') }}</option>
					<option v-for="t in data.enums.txn_type"
						:key="t" :value="t">{{ t }}</option>
				</select>
				<select class="form-control input-sm" v-model="presetKey">
					<option v-for="(p, k) in PRESETS" :key="k" :value="k">{{ p.label }}</option>
				</select>
				<button class="btn btn-default btn-sm" @click="load" :disabled="loading">
					{{ __('Refresh') }}
				</button>
				<button class="btn btn-default btn-sm"
					@click="revalidateAll"
					:disabled="loading || !data.mutationAllowed">
					{{ __('Validate Import') }}
				</button>
				<button class="btn btn-primary btn-sm"
					@click="bulkModalOpen = true"
					:disabled="loading || !data.mutationAllowed || selected.size === 0">
					{{ __('Set Party ({0})', [selected.size]) }}
				</button>
				<span class="cre-counters text-muted">
					{{ data.counters.total }} rows ·
					{{ data.counters.valid }} valid ·
					{{ data.counters.posted }} posted ·
					{{ data.counters.failed }} failed ·
					{{ data.counters.skipped }} skipped ·
					<span :class="data.mutationAllowed ? 'text-success' : 'text-warning'">
						{{ data.status }}
					</span>
				</span>
			</div>

			<div class="cre-grid-wrap">
				<table class="table table-bordered cre-grid">
					<thead>
						<tr>
							<th class="cre-col-sr">{{ __('Sr') }}</th>
							<th class="cre-col-check">
								<input type="checkbox"
									:checked="allFilteredSelected"
									@change="toggleSelectAll($event.target.checked)" />
							</th>
							<th>{{ __('Status') }}</th>
							<th v-for="col in effectivePresetCols" :key="col">{{ COLUMN_LABELS[col] || col }}</th>
							<th>{{ __('Action') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in filteredRows"
							:key="row.row_idx"
							:class="{ 'cre-row-selected': selected.has(row.row_idx) }">
							<td class="cre-col-sr">{{ row.row_idx }}</td>
							<td class="cre-col-check">
								<input type="checkbox"
									:checked="selected.has(row.row_idx)"
									@change="toggleSelect(row.row_idx, $event.target.checked)" />
							</td>
							<td><StatusPill :row="row" /></td>
							<td v-for="col in effectivePresetCols" :key="col"
								:class="{ 'cre-cell-editable': col === 'resolved_party' && data.mutationAllowed && !row.posted_docname && row.revert_status !== 'Reverted' }"
								:title="col === 'resolved_party' && data.mutationAllowed ? __('Double-click to edit party') : ''"
								@dblclick="col === 'resolved_party' && startPartyEdit(row)">
								<template v-if="col === 'resolved_party' && editingParty.rowIdx === row.row_idx">
									<div class="cre-inline-edit">
										<select v-model="editingParty.partyType"
											class="form-control input-sm cre-inline-type">
											<option value="Customer">Customer</option>
											<option value="Supplier">Supplier</option>
										</select>
										<PartyPicker :party-type="editingParty.partyType"
											v-model="editingParty.party" />
										<button class="btn btn-xs btn-primary"
											@click="savePartyEdit(row)"
											:disabled="!editingParty.party || loading">
											{{ __('Save') }}
										</button>
										<button class="btn btn-xs btn-default"
											@click="cancelPartyEdit">&times;</button>
									</div>
								</template>
								<template v-else>{{ formatCell(row, col) }}</template>
							</td>
							<td>
								<button v-if="row.validation_error_code"
									class="btn btn-xs btn-default"
									@click="openFixModal(row)">
									{{ __('Fix') }}
								</button>
							</td>
						</tr>
						<tr v-if="filteredRows.length === 0">
							<td :colspan="effectivePresetCols.length + 4" class="text-center text-muted">
								{{ __('No rows match the current filter.') }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<FixModal v-if="fixModalRow"
				:row="fixModalRow"
				:run-name="data.runName"
				:mutation-allowed="data.mutationAllowed"
				@close="fixModalRow = null"
				@row-updated="onRowUpdated" />

			<BulkPartyModal v-if="bulkModalOpen"
				:run-name="data.runName"
				:selected-rows="selectedRows"
				:mutation-allowed="data.mutationAllowed"
				@close="bulkModalOpen = false"
				@rows-updated="onRowsUpdated" />
		</template>
	</div>`,
};

// ── Mount entry ───────────────────────────────────────────────────────────────

function injectStyles() {
	if (document.getElementById("cre-styles")) return;
	const css = `
	.cre-root { padding: 0.5rem 1rem; display: flex; flex-direction: column;
		height: calc(100vh - 140px); }
	.cre-empty { padding: 2rem; color: var(--text-muted); }
	.cre-toolbar { display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;
		margin-bottom:0.75rem; flex: 0 0 auto; }
	.cre-toolbar .cre-search { flex: 1 1 240px; max-width: 360px; }
	.cre-toolbar select.form-control { width: auto; }
	.cre-counters { margin-left: auto; font-size: 0.85rem; }
	.cre-grid-wrap { overflow: auto; flex: 1 1 auto; min-height: 0;
		border: 1px solid var(--border-color, #ddd); border-radius: 4px; }
	.cre-grid { font-size: 0.85rem; margin-bottom: 0; }
	.cre-grid thead th { position: sticky; top: 0; background: var(--bg-color, #fff);
		z-index: 1; box-shadow: inset 0 -1px 0 var(--border-color, #ddd); }
	.cre-grid th, .cre-grid td { white-space: nowrap; vertical-align: middle; }
	.cre-grid td { max-width: 320px; overflow: hidden; text-overflow: ellipsis; }
	.cre-grid .cre-col-sr { width: 48px; text-align: right;
		font-variant-numeric: tabular-nums; color: var(--text-muted); }
	.cre-grid .cre-col-check { width: 28px; }
	.cre-row-selected { background: var(--bg-blue, #eef5ff) !important; }
	.cre-cell-editable { cursor: pointer; }
	.cre-cell-editable:hover { background: var(--bg-light-gray, #f5f5f5); }
	.cre-inline-edit { display: flex; gap: 4px; align-items: center; min-width: 280px; }
	.cre-inline-edit .cre-inline-type { width: 95px; }
	.cre-inline-edit .cre-party-picker { flex: 1; }
	.cre-pill { display:inline-block; padding: 1px 8px; border-radius: 8px;
		font-size: 0.75rem; font-weight: 500; }
	.cre-pill-green { background: #d4f7d4; color: #156815; }
	.cre-pill-red   { background: #ffd5d5; color: #8a1414; }
	.cre-pill-gray  { background: #e6e6e6; color: #555; }
	.cre-pill-blue  { background: #d3e8ff; color: #0a4f95; }
	.cre-pill-amber { background: #ffeac2; color: #7a4a00; }
	.cre-modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.45);
		display:flex; align-items:center; justify-content:center; z-index: 9999; }
	.cre-modal { background: var(--card-bg, #fff); border-radius: 6px;
		min-width: 420px; max-width: 600px; width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
	.cre-modal-header { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color, #ddd);
		display:flex; align-items:center; gap:0.5rem; }
	.cre-modal-header .cre-modal-code { color: var(--text-muted); font-size: 0.8rem;
		margin-left: auto; padding-right: 0.5rem; }
	.cre-modal-body { padding: 1rem; }
	.cre-modal-body label { font-weight: 500; font-size: 0.85rem; display:block; }
	.cre-modal-footer { padding: 0.5rem 1rem; border-top: 1px solid var(--border-color, #ddd);
		display:flex; gap:0.5rem; justify-content:flex-end; }
	.cre-party-picker { margin-top: 0.25rem; }
	`;
	const style = document.createElement("style");
	style.id = "cre-styles";
	style.textContent = css;
	document.head.appendChild(style);
}

window.cashew_mount_row_explorer = function (el, props) {
	injectStyles();
	const app = createApp(App, { runName: props.run_name });
	app.config.globalProperties.__ = window.__ || ((s) => s);
	app.mount(el);
	return app;
};
