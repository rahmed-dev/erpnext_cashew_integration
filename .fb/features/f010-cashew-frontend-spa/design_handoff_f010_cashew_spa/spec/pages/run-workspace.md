# Page: Run Workspace

> **Stack:** Vue 3 SPA (frappe-ui)
> **Component ID:** `c006` (`run-workspace-page`)
> **Routes:** `/runs/new` AND `/runs/:run_name`
> **Shell:** see [`../shell.md`](../shell.md) — sidebar + app switcher always present
> **Arch refs:** D5 (API discipline), D6 (session-only state), D7 (Run Workspace owns row-level UX natively — no Row Explorer link), D8 (realtime), D10 (state-driven sections), D11 (full row-level UX + extensible registries)

---

## 1. Page brief (for Claude Design)

The **operator's workspace for one Cashew Import Run** — from CSV upload all the way to "posted to the GL". This is where the bulk of operator time is spent during an import day. The same page renders different content based on the run's lifecycle state, so the operator never feels like they're navigating between unrelated screens — they're always "in this run", and the page evolves with their progress.

**Lifecycle states the page covers (4 sections, picked by `run.status`):**

| `run.status` | Section rendered | Operator's mental task |
|---|---|---|
| `Draft` *(or `/runs/new` with no record yet)* | **UploadSection** | "Drop a CSV, parse it." |
| `Parsed` | **PreviewSection** | "Look at the rows, run validation." |
| `Validated` | **RowsWorkbench** *(in "ready" mode)* | "Fix what's wrong, queue it." |
| `Queued` / `Processing` | **RowsWorkbench** *(in "live progress" mode)* | "Watch it post. Maybe cancel." |
| `Completed` / `Failed` / `Cancelled` / `Reverted` / `Revert-Failed` | **CompletedSummary** | "Verify the result. Revert if needed." |
| `Reverting` | **CompletedSummary** *(with progress)* | "Watch revert finish." |

The header is the same across all states (run name + status + actions). The content area swaps.

**Inspirations:** GitHub Actions workflow run page (state-driven, single URL, same chrome); Linear's issue detail (workspace feel rather than form feel); Stripe's payment detail (status banner + sections).

**Tone:** focused workspace. Quiet when there's nothing to do, but capable of presenting a dense data grid (the row workbench) without feeling cramped.

---

## 2. Audience & flow

**Primary:** finance operators doing the monthly Cashew → ERPNext import.

**Canonical happy-path flow (single sitting):**

```
sidebar "Imports"  →  click "+ New Import"
   ↓
/runs/new          →  UploadSection
   ↓                  (pick CSV, click "Parse")
   ↓                  (API: parse_and_preview → status flips to Parsed,
   ↓                   router.replace to /runs/CASHEW-IMPORT-...)
/runs/:name        →  PreviewSection
                      (eyeball the preview, click "Validate")
                      (API: validate_import → status Validated)
                      ↓
                      RowsWorkbench
                      (filter, fix rows, set parties, search,
                       resolve validation errors, click "Queue")
                      (API: queue_run → status Queued → Processing)
                      ↓
                      RowsWorkbench (live progress mode)
                      (rows flip Posted in real time via Socket.IO)
                      ↓
                      CompletedSummary
                      (verify counts, optionally Revert)
```

**Re-entry flow:** operator opens an existing run from the imports list — page lands in whichever section corresponds to current `run.status`. No "where am I?" confusion.

---

## 3. Layout

Sticky run header at top. Content area below swaps based on state.

```
┌───────────────────────────────────────────────────────────┐
│ A. Run Header                                  ─────────  │
│   ← Back   CASHEW-IMPORT-2026-000017  [Completed]         │
│   Company · Period · counts · action buttons             │
├───────────────────────────────────────────────────────────┤
│ B. State Stepper (optional, top edge of content area)     │
│   ① Upload — ② Preview — ③ Workbench — ④ Done             │
├───────────────────────────────────────────────────────────┤
│                                                           │
│                    STATE-DRIVEN CONTENT                   │
│             (UploadSection / PreviewSection /             │
│              RowsWorkbench / CompletedSummary)            │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

Run Header (A) and State Stepper (B) are constant. The big body switches.

Responsive: header stacks on mobile (status pill below name). Content area: each section's responsive notes below.

---

## 4. Shared chrome (constant across all states)

### A. RunHeader

**Purpose:** Always-visible identity + status + run-level actions.

**Layout:** Two rows.

**Row 1 — identity:**
| Element | Value | Source |
|---|---|---|
| Back chevron | `<` icon | routes to `/runs` |
| Run name | `CASHEW-IMPORT-2026-000017` | `name` (or `(new import)` when on `/runs/new` before parse) |
| Status pill | colored pill | `status` (see shared `StatusPill`) |
| Realtime tag (when active) | small "● Live" dot | shown when Socket.IO subscribed |
| "Open in Desk" | small link icon | routes to `/app/cashew-import-run/:name` (escape hatch) |

**Row 2 — metadata + actions:**

Left side — facts:
| Field | Source | Format |
|---|---|---|
| Company | `Cashew Import Run.company` | text |
| Period | `period_start` + `period_end` | "Apr 1 – Apr 30, 2026"; `—` if not yet parsed |
| Counts | `rows_total`, `rows_valid`, `rows_failed`, `rows_posted`, `rows_skipped` | "126 rows · 124 valid · 2 failed · 124 posted" — only non-zero shown |
| Started / Finished | `started_on`, `finished_on` | shown only when relevant; "Started 2h ago · Finished 1h ago" |

Right side — actions (state-dependent):

| State | Primary action | Secondary actions |
|---|---|---|
| `Draft` (or `/runs/new`) | `Parse` (disabled until file picked) | Delete draft *(only if record exists)* |
| `Parsed` | `Validate` | Re-parse · Discard |
| `Validated` | `Queue Import` | Re-validate · Discard |
| `Queued` / `Processing` | `Cancel` (danger) | — |
| `Completed` | `Revert` (danger, w/ confirm) | Download diagnostics CSV |
| `Failed` | `Re-validate` | Download diagnostics CSV · Discard |
| `Cancelled` | `Re-queue` | Discard |
| `Reverting` | (none — show progress) | — |
| `Reverted` | — | Re-queue · Discard |
| `Revert-Failed` | `Retry Revert` | Open in Desk |

**API mappings (D5 rule 3 — writes via `cashew_integration/api.py`):**

| Action | Endpoint | Confirm dialog? |
|---|---|---|
| Parse | `parse_and_preview(run_name)` | no |
| Validate | `validate_import(run_name)` | no |
| Re-validate | `validate_import(run_name)` | no |
| Queue Import | `queue_run(run_name)` | yes — "Post N rows to the GL?" |
| Cancel | `cancel_run(run_name)` | yes |
| Revert | `revert_run(run_name)` | yes (danger) — "This will reverse all posted JEs." |
| Retry Revert | `revert_run(run_name)` | yes |
| Delete draft / Discard | direct doc delete via `frappe.client.delete` | yes |

**Behaviour:**
- Action buttons disable + show inline spinner during API call.
- Failure → shell toast + button re-enables.
- Success → status pill animates to new color; section content below auto-switches.

---

### B. StateStepper *(optional but recommended)*

**Purpose:** Tell the operator where in the lifecycle they are. Pure progress indicator — not clickable.

**Display:** Horizontal 4-step bar across the top of the content area, just below the header.

```
  ① Upload  ──  ② Preview  ──  ③ Workbench  ──  ④ Done
```

**Mapping:**
| Step | Active when `status` is |
|---|---|
| ① Upload | `Draft` (or `/runs/new`) |
| ② Preview | `Parsed` |
| ③ Workbench | `Validated`, `Queued`, `Processing` |
| ④ Done | `Completed`, `Failed`, `Cancelled`, `Reverting`, `Reverted`, `Revert-Failed` |

**Display rules:** completed steps in muted-green check, current step in accent color, future steps grey.

**Mobile:** stepper collapses to a single label like "Step 3 of 4: Workbench".

---

## 5. State sections (content area)

### Section I — UploadSection
*Rendered when `status = Draft` OR route is `/runs/new` with no run record yet.*

**Purpose:** Get a CSV file uploaded and parse it.

**Layout:** Centered card on an otherwise mostly-empty content area. Generous whitespace.

#### Components

**I.1 CompanyPicker** *(only on `/runs/new` before record exists)*
| Field | Source | Default | Notes |
|---|---|---|---|
| Company | `Cashew Import Run.company` (Link to `Company`) | `boot.default_company` | frappe-ui Autocomplete per D5 rule 2 |

Hidden once the record exists (company is locked at creation).

**I.2 CsvDropzone**
| Element | Notes |
|---|---|
| Big drop area | drag-and-drop OR click to pick |
| Icon | upload-cloud (lucide) |
| Headline | `Drop your Cashew CSV here` |
| Sub | `or click to browse` |
| Filetype hint | `Accepted: .csv (Cashew app export)` |
| Selected file preview | filename, size, ✗ to remove |

**Field bound:** `Cashew Import Run.source_file` (Attach). Uses Frappe's `/api/method/upload_file` endpoint with `is_private=1`.

**I.3 OptionalConfigDisclosure** *(collapsible "Advanced" section)*
| Field | Source | Default | Notes |
|---|---|---|---|
| Balance Adjustment Account | `Cashew Import Run.balance_adjustment_account` (Link to `Account`) | from Cashew Settings or empty | Autocomplete |
| JV Rounding Tolerance | `Cashew Import Run.je_rounding_tolerance` (Currency) | `0.01` | number input |

**I.4 PrimaryActions**
- `Parse →` button — disabled until file is picked
- Cancel link — `/runs` (back to list)

**Behaviour on Parse:**
1. If on `/runs/new`: POST to create a `Cashew Import Run` doc with `company` + uploaded `source_file` → get back `name`.
2. Call `parse_and_preview(run_name)`.
3. On success: `router.replace('/runs/' + name)`. `run.status` is now `Parsed` → page auto-renders PreviewSection.
4. On failure: shell toast w/ error; stay on UploadSection; show the error inline below the dropzone too.

**States:** Default (empty) / file-picked / parsing (button spinner, dropzone disabled) / parse-error inline.

**Responsive:** Same as desktop, but dropzone takes full width and "advanced" stays collapsed by default on mobile.

---

### Section II — PreviewSection
*Rendered when `status = Parsed`.*

**Purpose:** Show the operator the parsed rows so they can sanity-check before validation.

**Layout:** Stats bar at top, table below.

#### Components

**II.1 ParseStatsBar**

Horizontal row of tiles summarizing parse results.

| Tile | Value | Source |
|---|---|---|
| Total rows | `rows_total` | `Cashew Import Run.rows_total` |
| Period | `period_start` – `period_end` | run fields |
| Income rows | count where `txn_type = "Income"` | client-side from preview rows OR a returned breakdown |
| Expense rows | count where `txn_type = "Expense"` | same |
| Transfers | count where `txn_type in ("Transfer", "External Transfer")` | same |
| Loans | count where `txn_type in ("Loan Receivable", "Loan Payable")` | same |
| Adjustments | count where `txn_type = "Adjustment"` | same |
| Duplicates | count where `is_duplicate = 1` | same |

**II.2 PreviewTable**

A read-only table of all parsed rows. Same component as RowsWorkbench's table, but in **preview mode**: no row-level actions, no inline edit, no bulk select. Just look.

Columns (preview mode default visible):
1. `#` (`row_idx`)
2. `Date` (`txn_date`)
3. `Account` (`raw_account`)
4. `Amount` (`base_amount` w/ `company_currency`)
5. `Type` (`txn_type`)
6. `Category` (`category` + `sub_category` below in smaller text)
7. `Note` (`note`, truncated)

Pagination only (no filters in preview mode).

**II.3 PrimaryActions**
- `Validate →` button (action: `validate_import(run_name)`)
- Re-parse link (action: `parse_and_preview(run_name)` — re-reads source CSV)
- Discard link

**Behaviour on Validate:** `validate_import` returns rich result; status flips to `Validated`; page auto-renders RowsWorkbench.

**States:** Loading rows / Loaded / Empty (parse returned 0 rows — show empty state w/ Re-parse) / Error.

**Responsive:** Stats bar wraps; table collapses columns same as imports-list mobile rules.

---

### Section III — RowsWorkbench *(the heart of D11)*
*Rendered when `status = Validated, Queued, Processing`. Same table; mode shifts.*

**Purpose:** Operator fixes invalid rows, sets parties, manages bulk corrections, then queues the run. After queueing, the table becomes live (rows flip Posted as the worker processes them).

**Mode shifts driven by `status`:**
- `Validated` — full edit mode (inline edit, bulk actions, validate)
- `Queued` / `Processing` — read-mostly mode (no edits; live update of posted_doctype/posted_docname per row)

**Layout:**

```
┌──────────────────────────────────────────────────────────────────────┐
│ III.1 WorkbenchToolbar                                              │
│   [Search ──] [Filters ▾] [Columns ▾] [Bulk actions ▾]  [Validate]  │
├──────────────────────────────────────────────────────────────────────┤
│ III.2 ActiveFilterChips      "Status: Error ×"   "Type: Income ×"   │
├──────────────────────────────────────────────────────────────────────┤
│ III.3 RowsTable                                                     │
│   (large data grid — see column list below)                         │
├──────────────────────────────────────────────────────────────────────┤
│ III.4 SelectionFooter (only when 1+ rows selected)                  │
│   "8 rows selected"  [Set party…] [Re-validate selected] [Clear]    │
└──────────────────────────────────────────────────────────────────────┘
```

#### Components

**III.1 WorkbenchToolbar**

Horizontal toolbar. Left to right:

| Element | Purpose | Notes |
|---|---|---|
| `SearchInput` | Multi-word AND search across visible string columns | 250ms debounce; matches in hidden columns auto-extend the visible preset |
| `FiltersDropdown` | Multi-faceted filter menu (see below) | menu w/ filter facets |
| `ColumnsDropdown` | Show/hide columns; preset switcher | menu w/ "Reset to preset" |
| `BulkActionsDropdown` | Quick access to bulk operations (also available in SelectionFooter when selecting) | menu |
| spacer | | flex-grow |
| `Validate` button | Re-validates the whole run | calls `validate_import(run_name)` |

**Filters facets** *(implements D11 — declarative filter registry; each is a chip on click)*:

| Facet | Field | Type | Options |
|---|---|---|---|
| Validation Status | `validation_status` | Select | `Valid`, `Error`, `Skipped` |
| Transaction Type | `txn_type` | Select | `Income`, `Expense`, `Transfer`, `External Transfer`, `Adjustment`, `Loan Receivable`, `Loan Payable` |
| Category Type | (derived from `Cashew Category Mapping.category_type` via `category`) | Select | `Income`, `Expense`, `Loan Out`, `Loan In` |
| Category | `category` | string facet | unique values from rows |
| Raw Account | `raw_account` | string facet | unique values from rows |
| Posted | derived from `posted_docname` non-null | tri-state | Posted / Not posted / Failed (`revert_status = Revert-Failed` or `validation_status = Error`) |
| Has party | derived | tri-state | Has party / Missing party / N/A |
| Duplicate | `is_duplicate` | toggle | Yes / No / Any |

**Column presets** *(in ColumnsDropdown — registered declaratively per D11)*:
- `Compact` — Date, Account, Amount, Type, Category, Validation
- `Validation-focused` *(default when any row has errors)* — Date, Account, Amount, Validation, Error Message, Party
- `Posting-focused` *(default once Validated)* — Date, Account, Amount, Type, Resolved Account, Party, Validation
- `Wide` — everything

User can toggle individual columns on top of any preset.

**Bulk actions** *(extensible registry per D11)*:
- Set party (opens modal — see below)
- Re-validate selected rows
- *(future actions plug in here — Set category, Mark duplicate, etc.)*

**III.2 ActiveFilterChips**
Shows currently active filters as removable chips. "Clear all" link on the right when any active.

**III.3 RowsTable**

The main data grid. Sticky header. Sticky `Sr` column. Horizontal scroll for wide column sets.

**All possible columns** *(declarative; ColumnsDropdown picks visibility):*

| Col | Header | Field | Type | Behaviour |
|---|---|---|---|---|
| Sr | `#` | `row_idx` | int | sticky-left, tabular-nums |
| Sel | (checkbox) | — | bulk select | sticky-left next to Sr |
| Valid | `Status` | `validation_status` | Select | `StatusPill` colored by enum |
| Date | `Date` | `txn_date` | Date | format "May 2" |
| Time | `Time` | `raw_txn_time` | Time | "14:23" (hidden by default) |
| Account | `Account` | `raw_account` | Data | text |
| Amount | `Amount` | `base_amount` + `company_currency` | Currency | right-aligned, w/ sign by `income_flag` |
| Source Amt | `Source Amt` | `raw_amount` + `source_currency` | Currency | hidden by default |
| FX | `FX` | `exchange_rate` | Float | hidden by default |
| Type | `Type` | `txn_type` | Select | small text pill ("Income", "Expense", "Transfer", "Adjustment", "Loan Receivable", "Loan Payable") |
| Route | `Route` | `resolved_route` | Select | small grey badge; hidden by default |
| Category | `Category` | `category` + `sub_category` | Data | two-line cell |
| Item | `Item` | `item_label` | Data | hidden by default |
| Title | `Title` | `title` | Data | hidden by default |
| Note | `Note` | `note` | Small Text | truncated to 1 line, tooltip on hover |
| Resolved Account | `Resolved Account` | `resolved_account` | Link → Account | text |
| External Account | `External Account` | `resolved_external_account` | Link → Account | hidden by default; shown for Transfer rows |
| Party Required | `Party Reqd` | `requires_party` | Check | small icon (✓ or —); hidden by default |
| Party Type | `Party Type` | `resolved_party_type` | Select | Customer / Supplier / None |
| Party | `Party` | `resolved_party` | Dynamic Link | **inline-editable** when `validation_status != Valid` or operator double-clicks; see III.5 |
| Validation Err | `Error` | `validation_error_message` | Small Text | red text; truncated with full message in tooltip |
| Error Code | `Code` | `validation_error_code` | Data | small grey badge; hidden by default |
| Posted DocType | `Posted As` | `posted_doctype` | Select | "Journal Entry", "Sales Invoice", etc. |
| Posted Doc | `Posted Doc` | `posted_docname` | Dynamic Link | clickable link → opens posted doc in Desk new tab |
| Posted GL Date | `Posted GL` | `posted_gl_date` | Date | hidden by default |
| Duplicate | `Dup` | `is_duplicate` | Check | small icon when true; hidden by default |
| Revert | `Revert` | `revert_status` + `revert_error` | Select + Small Text | shown only when run was reverted; pill + tooltip |

**Per-row actions (kebab menu in last column):**
- View row JSON (debug; opens drawer with all fields)
- Re-validate this row (`row_explorer_revalidate(run_name, [row_idx])`)
- Open posted doc in Desk (when `posted_docname` set)
- Fix this row… (opens validation-fix modal — see III.4 below)

**Row click:** opens **InlineRowDrawer** on the right (full row details) — non-destructive.

**Row double-click on Party cell:** activates inline edit (see III.5 — InlinePartyEdit).

**Row color cues:**
- `validation_status = Error` → row left-border red
- `validation_status = Skipped` → row left-border grey
- `is_duplicate = 1` → row faded slightly
- `posted_docname` set → row left-border green
- New row added during realtime → brief pulse highlight

**III.4 ValidationFixModal**
*Triggered by per-row "Fix this row…" or by clicking the Error pill.*

**Layout:** Modal dialog, ~640px wide.

**Header:** `Fix row #{row_idx}` + close icon.

**Body:**
- **Error summary** — `validation_error_code` (small badge) + `validation_error_message` (full text).
- **Row context** (read-only) — Date, Account, Amount, Type, Category. Compact.
- **Editable fields** (which fields are editable depends on the error code; v1 covers the common ones):
  | Field | When shown |
  |---|---|
  | `resolved_account` (Link → Account) | when error implies missing/wrong account |
  | `resolved_party_type` (Select Customer/Supplier) + `resolved_party` (Dynamic Link) | when error code = `MISSING_PARTY` |
  | `resolved_external_account` (Link → Account) | for transfer error |
- **Footer:**
  - Cancel (left)
  - `Save & Re-validate` (primary) — saves the changes, calls `row_explorer_revalidate(run_name, [row_idx])`, modal closes if row becomes Valid; otherwise stays open with new error.

**III.5 InlinePartyEdit**

Triggered by double-clicking the Party cell on any row.

**Display:** Cell turns into a two-input row:
- `resolved_party_type` — small select (Customer / Supplier / None)
- `resolved_party` — frappe-ui `<Autocomplete>` with `reference_doctype = resolved_party_type` (D5 rule 2; filter by `disabled = 0`)

**Behaviour:**
- Tab moves between the two
- `Enter` saves (calls `row_explorer_set_party(run_name, [row_idx], party_type, party)`)
- `Esc` cancels
- Cell shows spinner during save
- After save: if `validation_status` changes (server-side re-validates), row updates accordingly

**III.6 SelectionFooter**

Sticky at the bottom of the table when any row is selected (via checkbox).

| Element | Notes |
|---|---|
| Count chip | "8 rows selected" |
| `Set party…` button | Opens BulkPartyModal (see III.7) |
| `Re-validate selected` button | Calls `row_explorer_revalidate(run_name, row_indices)` |
| `Clear selection` link | Unchecks all |

**III.7 BulkPartyModal**

**Triggered by:** `Set party…` from SelectionFooter or BulkActionsDropdown.

**Header:** `Set party for {N} selected rows`.

**Body:**
- `Party Type` — select (Customer / Supplier)
- `Party` — frappe-ui Autocomplete (filtered by chosen type)
- Hint: `Existing party values on selected rows will be overwritten.`

**Footer:** Cancel · `Set party` (primary) — calls `row_explorer_set_party(run_name, row_indices, party_type, party)`.

Result: bulk save, modal closes, affected rows update, optionally a toast "Set party 'ACME Corp' on 8 rows".

#### Workbench states

| State | Look |
|---|---|
| Validating | Validate button shows spinner; table content stays; banner: "Validating rows…" |
| All valid + Queue available | Banner: "All {N} rows valid. Ready to queue." + green left bar; Queue button in header is primary. |
| Some errors | Banner: "{N} rows have validation errors." + red dot; default filter set to `Status: Error`. |
| Queued | Banner: "Queued at {time}, waiting for worker…" + Cancel button in header. |
| Processing | Live progress bar: "{rows_posted} of {rows_total} posted"; rows update in real time. |
| Empty (no rows at all — shouldn't happen but defensive) | "This run has no rows. Re-parse the CSV." |

#### Workbench responsive notes

| Breakpoint | Layout |
|---|---|
| ≥1280px | Full toolbar, sticky header table, all default-visible columns. |
| 1024–1279px | Toolbar wraps to 2 rows if needed. Some columns collapse into kebab "details". |
| 768–1023px | Filter dropdown collapses into single "Filters" button (bottom-sheet on click); search input full width above table. Columns auto-fit. |
| <640px | Rows render as **cards** instead of a table. Each card shows: Sr · Date · Amount · Type · Category · Validation pill · Party (editable on tap-hold or via Fix modal). Bulk selection via tap-and-hold; SelectionFooter slides up. ValidationFixModal becomes a full-screen sheet. |

---

### Section IV — CompletedSummary
*Rendered when `status in (Completed, Failed, Cancelled, Reverting, Reverted, Revert-Failed)`.*

**Purpose:** Show the result of the run, let the operator verify counts and revert if needed.

**Layout:**

```
┌──────────────────────────────────────────────────────────────────┐
│ IV.1 ResultBanner                                                │
│   ✓  Completed — 124 rows posted (2 failed)                      │
│   Started 2h ago · Finished 1h ago                               │
├──────────────────────────────────────────────────────────────────┤
│ IV.2 CountsGrid                                                  │
│   [Total][Valid][Posted][Failed][Skipped]                        │
├──────────────────────────────────────────────────────────────────┤
│ IV.3 PostedBreakdown                                             │
│   By Posted DocType (Sales Invoice / JE / Transfer JV / …)       │
├──────────────────────────────────────────────────────────────────┤
│ IV.4 RowsTable (read-only mode of III.3)                         │
│   Default filter: Posted = Failed/Reverted; toggle "Show all"    │
├──────────────────────────────────────────────────────────────────┤
│ IV.5 DangerZone                                                  │
│   Revert this import   /   Download diagnostics                  │
└──────────────────────────────────────────────────────────────────┘
```

#### Components

**IV.1 ResultBanner**
| Field | Value |
|---|---|
| Icon + headline | per status — ✓ Completed / ⚠ Partial / ✗ Failed / 🔄 Reverted / etc. |
| Sub | "{rows_posted} rows posted, {rows_failed} failed, {rows_skipped} skipped" |
| Timestamps | `started_on`, `finished_on` |

Color: green (Completed), amber (Cancelled / Reverted), red (Failed / Revert-Failed).

**IV.2 CountsGrid**
Same idea as PreviewSection.ParseStatsBar — but with the post-run counts: total, valid, posted, failed, skipped. Each value from `Cashew Import Run.rows_*`.

**IV.3 PostedBreakdown**
Pie or list showing how many rows posted as each doctype.

Sources (derived from `Cashew Import Row.posted_doctype` over all rows of this run):
| Posted DocType | Count |
|---|---|
| Journal Entry | n |
| Sales Invoice | n |
| Purchase Invoice | n |
| Transfer JV | n |
| External Transfer JE | n |
| Adjustment JE | n |
| Loan Receivable JE | n |
| Loan Payable JE | n |
| *(no doctype — failed/skipped)* | n |

Optional click on a slice → applies filter to the RowsTable below.

**IV.4 RowsTable (read-only)**
Same component as III.3 but locked to read-only mode (no inline edit, no bulk actions). Default filter: `Posted = Failed/Reverted` — operator sees problems first. Toggle `Show all rows` to expand.

Columns shifted to the **Posting-focused** preset.

**IV.5 DangerZone**
Card with subdued red accent.
- Headline: `Revert this import` (only when `status = Completed`)
- Body: `This will reverse every posted document. The original CSV file will remain attached.`
- Button: `Revert →` (danger button) → confirm dialog → `revert_run(run_name)`
- Secondary: `Download diagnostics CSV` → `Cashew Import Run.diagnostics_file` URL

For other terminal states:
- `Failed` → Re-validate / Re-queue buttons + diagnostics
- `Cancelled` → Re-queue button
- `Reverting` → no danger zone; show progress bar
- `Reverted` → "Re-queue" (re-runs from Validated state) or "Discard"
- `Revert-Failed` → Retry Revert + Open in Desk for manual cleanup

---

## 6. Realtime (per D8)

The page subscribes to `Cashew Import Run` `doc_update` events scoped to the **currently-viewed run** on mount.

**What can change live:**
- `status` (drives section swap — operator sees Processing → Completed without refreshing)
- `rows_total`, `rows_valid`, `rows_posted`, `rows_failed`, `rows_skipped` (counter updates)
- Individual `Cashew Import Row` fields — `validation_status`, `posted_doctype`, `posted_docname`, `revert_status` (table updates in place)

**Connection state** reflected by the shell's `RealtimeStatusIndicator`.

**Degraded mode:** On permanent socket loss, fall back to polling `get_run_progress(run_name)` every 30 seconds (D8 fallback). Connection indicator switches to "Polling".

---

## 7. Page-level states & transitions

| Scenario | Behaviour |
|---|---|
| Direct deep-link to `/runs/CASHEW-IMPORT-...` | Fetch run → render section by `status`. |
| `/runs/new` first load | UploadSection w/ CompanyPicker; no run record yet. |
| Parse succeeds | Status flips to `Parsed`; `router.replace` to `/runs/:name` (not push — prevents back-button to `/runs/new` with stale state, per D10.b). PreviewSection renders. |
| Validate succeeds | Status `Validated`; RowsWorkbench renders. |
| Queue succeeds | Status `Queued`; RowsWorkbench renders in live-progress mode; banner shows progress. |
| Worker posting | Realtime updates per-row + counters. |
| Run completes | Status `Completed`; CompletedSummary renders. |
| Revert clicked | Confirm → `revert_run`; status `Reverting`; CompletedSummary stays w/ progress. |
| Revert completes | Status `Reverted`; CompletedSummary shows reverted banner. |
| Error in any API call | Shell toast (D5.c); affected section shows inline error; user can retry. |

---

## 8. Data sources (per section)

### Run header + entire page
`frappe.client.get_doc('Cashew Import Run', name)` on mount. Includes `import_rows` child table.

### Upload section
- Frappe `/api/method/upload_file` (file upload)
- `frappe.client.set_value` or `frappe.client.insert` if creating a new run
- `cashew_integration.api.parse_and_preview` (Parse action)

### Preview section
- `cashew_integration.api.validate_import` (Validate action)
- Preview rows come from `import_rows` already in the run doc

### Workbench
- Initial rows: from `import_rows` already in the run doc — OR `cashew_integration.api.row_explorer_load(run_name)` if a more efficient projection is desired (already exists from f006; TD-time pick)
- `cashew_integration.api.row_explorer_set_party(run_name, row_indices, party_type, party)` (inline + bulk)
- `cashew_integration.api.row_explorer_revalidate(run_name, row_indices)` (per-row + bulk)
- `cashew_integration.api.validate_import(run_name)` (full re-validate)
- `cashew_integration.api.queue_run(run_name)` (Queue)
- `cashew_integration.api.cancel_run(run_name)` (Cancel)

### CompletedSummary
- `cashew_integration.api.revert_run(run_name)` (Revert)
- `cashew_integration.api.get_run_progress(run_name)` (poll fallback)

### Party selectors
- frappe-ui `<Autocomplete>` with `reference_doctype = "Customer"` or `"Supplier"`, `reference_fieldname = "resolved_party"` (D5 rule 2 — preserves any `get_query` registered for that field).

---

## 9. Accessibility

- State sections announce as `<section aria-labelledby>` regions
- Section swap on status change announces via `aria-live="polite"` ("Status changed to Processing")
- Workbench table is a proper `<table>` with `<thead>` and `aria-sort`
- Inline party edit is keyboard-driven (Tab between fields, Enter saves, Esc cancels)
- Modal dialogs trap focus, return focus to triggering element on close
- All colored pills have explicit text labels — color is never the only signal
- Selection checkboxes have `aria-label="Select row {row_idx}"`

---

## 10. Shared components used

| Shared component | Where | See |
|---|---|---|
| `StatusPill` | Run header status, row Validation Status, Type pills, Posted indicators | `../shared-components.md` |
| `AmountDisplay` | Amount, Source Amt columns; counts grid; result banner | `../shared-components.md` |
| `PageHeader` | RunHeader (Section A) is a specialized PageHeader | `../shared-components.md` |
| `EmptyState` | empty preview / empty workbench / etc. | `../shared-components.md` |
| `SkeletonBlock` | loading rows + tiles | `../shared-components.md` |
| `ConfirmDialog` | Queue / Cancel / Revert confirmations | `../shared-components.md` |
| `DateRange` | Period display + period picker | `../shared-components.md` |

---

## 11. DocType field requests *(open flag from arch UI-phase)*

Captured here for Architect/Dev review. None are blocking; mark with **priority** per item.

| Priority | Field | DocType | Type | Why UX needs it |
|---|---|---|---|---|
| Low | `notes` (operator notes about this run) | `Cashew Import Run` | Small Text | Operator wants to leave a note on a run ("imported with Acme's revised April export"); currently no place to put it. Would render in Run Header row 2. |
| Low | `row_note` (per-row operator note) | `Cashew Import Row` | Small Text | When fixing rows, operator wants to record why they set a particular party — for next month's audit. |
| Medium | `validation_severity` (Error / Warning / Info) | `Cashew Import Row` | Select | Today `validation_status` only has Valid/Error/Skipped. A "Warning" severity would let the workbench surface non-blocking issues (e.g. "unusually large amount for this category"). Improves the operator's signal-to-noise. |

**These are flagged for Architect/Dev approval per the arch UI-phase scope flag. Not auto-approved. UI will not break if none of them ship.**

---

## 12. Out of scope (v1)

- Editing parsed row data other than the party fields (no inline amount edits, no inline category edits — those require a re-parse of source CSV).
- Splitting one source row into multiple posted documents.
- Merging two source rows into one posted document.
- Operator-defined column layouts saved across sessions (D6 — session-only).
- Auto-save of bulk-action draft state on browser close.
- Comments / discussion threads on a run.
- Per-row attachments.

---

## 13. Designer notes (Claude Design)

- The page must feel like a **workspace**, not a form. Generous, not boxed-in.
- The state stepper is small — it's a confidence indicator, not the main UI.
- The RowsWorkbench is the hardest design problem on this whole app. Lean on tight table density, generous filter UX, and very clear status colors. Linear and Stripe's data grids are the right reference.
- Validation errors should feel urgent but not aggressive — red, but inline, not yelling.
- Inline party edit should feel instant — operators will do this dozens of times in a single session.
- The danger zone in CompletedSummary should genuinely feel cautious — Revert is destructive (reverses GL entries).
- Bulk SelectionFooter should be unmissable when active — it's the operator's superpower for batch fixes.
