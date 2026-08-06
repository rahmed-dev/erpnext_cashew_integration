# Import integrity — fixes shipped 2026-08-07

Companion to `import-integrity-2026-08-07.md`, which reports the findings. This
records what was changed and what still needs a human decision.

The findings were not six unrelated bugs. Four of them share one root: **the
importer was write-once.** It stamped a document name on a row and never looked
at that document again, and it computed derived values (exchange rate, base
amount) without writing them back. Nothing in the app could see the difference
between what it claimed and what the ledger said. So the central change is not a
patch to any one path — it is giving the app the ability to re-read its own work.

## Code changes

### `importer/reconcile.py` — new

The self-audit the app never had.

- `on_document_cancelled` / `on_document_trashed` — wired to `Journal Entry`
  `doc_events` in `hooks.py`. The moment a Cashew-posted document is cancelled or
  deleted outside the revert flow, the owning row is stamped
  `revert_status = "Cancelled Externally"` / `"Deleted Externally"` with an
  explanatory `revert_error`. `frappe.flags.cashew_reverting`, set by the revert
  worker, keeps the app's own cancels from being misreported as external.
- `reconcile_run(run_name)` — read-only sweep. Re-reads every claimed document
  and reports missing / cancelled / draft / date-drifted ones, documents stamped
  with the run that no row claims, and counters that disagree with the child
  table. Exposed as `api.reconcile_run_integrity`.
- `reconcile_all_runs()` — daily `scheduler_events` entry. Drift surfaces on its
  own rather than waiting for someone to go looking.

`rows_posted` is deliberately exempt from drift on a reverted run — revert clears
`posted_docname` but the lifetime count stays meaningful. The exemption does
**not** extend to a run with no child rows at all, which is the phantom-duplicate
signature rather than a reverted run.

### `importer/posting.py` — same-currency foreign transfers

The `src_cur == dst_cur` branch now splits. Both legs in company currency keeps
the 1:1 shortcut, which was always correct for that case. Both legs in the *same
foreign* currency now looks the rate up via `_lookup_erp_rate` and errors the pair
with `TRANSFER_RATE_UNAVAILABLE` when none exists, instead of silently booking a
foreign amount into a company-currency column.

`post_transfer_pair` also stamps `exchange_rate` and `base_amount` back onto both
legs before the balance check. `apply_exchange_rates` skips Transfer rows on
purpose — the rate only exists once both legs are known — but nothing was writing
it back afterwards, so every transfer row read as `exchange_rate = 0`.

### `Cashew Import Run` — a new run cannot claim history

`no_copy: 1` on `status`, all five counters, `period_start/end`, `queued_job_id`,
`started_on`, `finished_on`, `diagnostics_file` and `import_rows`. Plus a
`validate()` guard that forces any run without a `creation` timestamp to Draft
with zeroed counters and cleared timestamps.

The guard tests `self.get("creation")` rather than `is_new()` on purpose:
`is_new()` reads the `__islocal` flag, which is only set on the insert path and is
`None` for a document built straight from a dict — the exact shape a duplicate
arrives in. Written with `is_new()` first, the guard silently did nothing; the
test caught it.

### `importer/opening.py` — new

`audit_opening_balances(company)` walks every leaf Cash/Bank account and reports
the lowest point its running balance reaches. Any account that dips below zero is
missing at least that much opening balance, and `suggested_minimum_opening` states
that lower bound. `post_opening_entry` writes the one-time ERPNext Opening Entry.
It refuses a foreign-currency account supplied without an exchange rate, which is
the same mistake finding 3 was about.

The app cannot know the true opening figure. Only the person who counted the cash
can — see below.

## Backfill patches (`patches.txt`, post_model_sync)

All three are data-only and write no GL.

| Patch | Repairs |
|---|---|
| `flag_externally_cancelled_rows` | Rows whose posted document is already cancelled or deleted — catches `ACC-JV-2026-00042` |
| `resync_run_counters` | Recomputes counters from the child table; zeroes `rows_posted` and the copied timestamps only when a run owns no rows *and* no documents — the unambiguous phantom case (run 000004) |
| `backfill_transfer_row_rates` | Recovers `exchange_rate` / `base_amount` on already-posted Transfer rows by reading them back out of the GL entry the row's own JE wrote |

Applied clean on `work.local`, which carries the same import history, and all
three recorded in Patch Log. Confirmed effects there:

- run 7 of `CASHEW-IMPORT-2026-000001` now reads `Cancelled Externally` against
  `ACC-JV-2026-00042` — the only row flagged, as expected
- `CASHEW-IMPORT-2026-000004` now reads `rows_total 0, rows_posted 0`, with
  `started_on` and `finished_on` cleared
- 0 transfer rows left at `exchange_rate = 0`, with recovered rates in the
  expected band (276.53, 276.95, 277.00 PKR/USD)

## Not automatic — needs a decision

### `scripts/repost_same_currency_transfers.py`

Correcting `ACC-JV-2026-00275` means cancelling a submitted JE and posting a
replacement. That is a GL write and never belongs in a migration, so it is an
explicit script with a dry run by default:

```
bench --site <site> execute \
  cashew_integration.scripts.repost_same_currency_transfers.run

bench --site <site> execute \
  cashew_integration.scripts.repost_same_currency_transfers.run \
  --kwargs "{'apply': True}"
```

It finds affected entries generically rather than by hardcoded name, and skips any
where no Currency Exchange rate exists for the date. On the live site this is one
entry, and fixing it clears Elevate Pay's -1,238.85.

### ~~Opening balances~~ — not needed

The full Cashew SQLite export settles this: Petty Cash opened at **0.28** on
2026-03-04 and ERPNext already holds exactly that; every other imported wallet
opened at zero. See the withdrawn finding 1 for the working. `importer/opening.py`
remains as a general capability with nothing to post for this company.

### `ACC-JV-2026-00042` — probably correct as cancelled

2026-03-26, Petty Cash, "PC Build", 13,750.00 PKR, expense, run
`CASHEW-IMPORT-2026-000001` row 7. Created 07:13:45 and cancelled 07:28:36 the same
morning by Administrator, fifteen minutes later.

Reconciled against Cashew, restoring it would move ERPNext *away* from the source
(-15,073.93 against Cashew's 0.07) rather than toward it. The fifteen-minute gap and
the direction of the error both point at a deliberate cancel of a duplicate.
Recommendation: leave it cancelled. The backfill now flags the row
`Cancelled Externally` so it reads as a decision rather than an unnoticed hole.

### Petty Cash: 1,324.00 PKR — resolved, and it was a real bug

Cashew says 0.07 on 2026-07-30; ERPNext says -1,323.93. A line-by-line diff of all 215
importer-created Petty Cash entries against the SQLite export leaves exactly three
unmatched lines, and Cashew's own timestamps explain them:

| UTC | |
|---|---|
| 2026-06-29 15:43:08 | Loan to Customer HC created at **150,000.00**, imported as `ACC-JV-2026-00565` |
| 2026-07-07 05:55:38 | Loan **edited down to 148,674.00** |
| 2026-07-07 05:55:55 | 17 seconds later, the 1,326.00 difference entered as its own transaction |

The loan was split. Cashew holds both halves; ERPNext imported the new 1,326.00 line
(created inside a later window) but never revisited the edited loan, so it still carries
150,000.00 and counts the 1,326.00 twice. With the PC Build's +2.00 — ERPNext has a
13,748.00 Purchase Invoice where Cashew noted 13,750.00 — that is exactly -1,324.00.

Two independent causes, both in `importer/sqlite_reader.py`:

1. `_normalize_row` windowed on `date_created` only. An edit does not move
   `date_created`, and `date_time_modified` was not even selected, so an edited older
   transaction fell outside every later window and was never seen again.
2. `_READER_SQL` read `transaction_pk` into `row["_txn_pk"]`, where the leading
   underscore made `api._dict_to_child` drop it and no doctype field existed to hold
   it. Idempotency therefore keyed on `source_hash` alone — and an edit *changes* the
   hash, so an edited row read as brand new rather than as a revision.

The same write-once root as the rest of f013. Fixed in c006 below.

## c006 — resync of edited source transactions

### `Cashew Import Row`

`source_pk` (Cashew `transaction_pk`) and `source_modified`, both `read_only` +
`no_copy`. `revert_status` gains `Resynced` and `Superseded`.

`source_pk` is stable across edits where `source_hash` is not, and the pair gives the
three-way answer the importer needed: unknown pk → new; known pk, same hash → duplicate,
skip; known pk, different hash → edited upstream, resync.

`source_pk` is deliberately **not** part of `parser._compute_hash`. The hash must
describe content only — a pk inside it would make every row unique and break
idempotency outright. `tests/test_sqlite_import.py`'s CSV/SQLite parity test pins this.

### `importer/sqlite_reader.py`

The window now admits a row whose created date **or** modified date falls inside it.
`txn_date` still comes from `date_created`, so a row kept only because it was edited
in-window still posts under its real transaction date.

`date_time_modified` is selected only when the backup's schema has the column
(`_reader_sql` checks `PRAGMA table_info`). Naming it unconditionally made sqlite raise
`OperationalError` on any older export, which the reader reported as "not a readable
Cashew SQLite backup" — a total import failure traded for an optional field. Caught by
the existing suite, which uses fixtures without the column.

### `importer/resync.py` — new

`mark_changed_rows` tags edited rows; `apply_resync` posts the replacement, then
cancels the stale document under `frappe.flags.cashew_reverting` so
`reconcile.on_document_cancelled` does not call the app's own cancel external. The old
row is stamped `Superseded`, the new one `Resynced`, each naming the other.

The user chose correction-during-import over flag-and-wait, so a routine import can now
rewrite submitted GL. That makes the guards the load-bearing part:

- **post before cancel.** Cancelling first and failing to repost would leave the period
  with neither entry — worse than the stale figure being corrected.
- **closed period** (disabled Fiscal Year or a Period Closing Voucher on/after the date)
  → `RESYNC_PERIOD_CLOSED`, nothing written.
- **repost fails** → `RESYNC_REPOST_FAILED`, original left submitted and untouched.
- prior document already cancelled or deleted → post as new, no second cancel.

Every guard errors the row rather than raising, so one bad row cannot abort a run. Each
resync is logged per run (`Cashew Import Resynced Edited Rows`) — an import that
rewrites submitted GL needs a trail somewhere a person will actually look.

### `importer/idempotency.py`

Change detection runs *before* the hash check, and a tagged row is exempt from the skip
— its new hash is genuinely absent from the ledger.

Also removed a dead line: `all_hashes = {r["raw_amount"] for r in rows}` was never used,
its comment claimed it held hashes, and it raised `KeyError` on any row without
`raw_amount`. A test fixture found it.

### SPA

- `StatusPill`'s `row-revert` table only knew `Reverted` and `Revert-Failed`, so the
  f013 c001 external states already rendered unstyled; it now carries all six.
- `RowsTable.vue` hand-rolled its own revert pill keyed on `Failed` and `Pending` —
  values this field cannot hold. Replaced with the shared pill.
- `InlineRowDrawer.vue` shows a notice explaining a cancelled-and-replaced document
  rather than leaving it to be pieced together from a status column and a field dump.

### Not backfilled

`source_pk` cannot be derived for rows already imported: CSV carries no transaction id
and the SQLite path discarded it. Existing rows keep `source_pk = NULL` and take the
unchanged hash-only path. **Detection starts with the next import; the existing history
is not protected.** Confirmed with the user, who will take care upstream instead.

### `scripts/correct_stale_loan_je.py`

The one known stale entry, corrected by hand. Identified by content, not name — it is
`ACC-JV-2026-00565` on live and was `ACC-JV-2026-00375` on work.local — and it refuses
to write unless exactly one row matches. Dry run by default, like the FX repost.

Expected: Petty Cash -1,323.93 → **+2.07**, Customer HC's receivable down 1,326.00. The
2.00 residual against Cashew's 0.07 is the PC Build invoice-versus-note difference and
is left alone.

### work.local cannot rehearse this

Correcting an earlier claim in this document: work.local is not merely behind, it is
**gutted** — 73 Journal Entries and 3 Cashew Import Rows, with both 150,000.00 Petty
Cash GL entries already cancelled. The earlier "165 Petty Cash entries" count included
cancelled ones. The dry run there correctly reports nothing to correct.

A fresh `erp.nstack.xyz` backup is therefore a hard prerequisite for Part A, not a nicety.
Until one exists, `correct_stale_loan_je` has been exercised only under mocks
(`tests/test_resync.py::TestStaleLoanMatcher`).

## c008 — coherence review of c006, and what it found

A read-through of `be5dd4a` before deploying it found six defects. Two broke the
ledger, and both came from one mistake: **resync was bolted on as a branch of the
worker's transaction-type switch rather than made a property of the import.**

| # | Defect | Consequence |
|---|--------|-------------|
| 1 | `worker._process` tested `txn_type == "Transfer"` before `_resync_of` | An edited transfer leg never reached the resync branch: it posted a second JV and left the stale one submitted — the exact double-count c006 exists to prevent |
| 2 | Reader window widened to created-OR-modified with no gate | A transaction dated before the window but edited inside it, with no prior posting, was posted as NEW — an August import could write November entries |
| 3 | `reconcile_run` reported every `docstatus == 2` as drift | Every run that ever resynced was permanently unclean, drowning the real signal |
| 4 | `apply_resync`'s two "post as new" fallbacks returned a truthy doctype | The worker counted a resync that never happened, and the audit log — filtered on `revert_status` — disagreed with the counter |
| 5 | `_write_row_result` wrote `revert_status` unconditionally | Re-queueing a Failed run erased any `Cancelled Externally` stamp reconcile had made |
| 6 | `rows_resynced` emitted to the SPA, stored nowhere | The count vanished on reload |

There was also a silent hole in c006 worth recording: the `.cancel()` sat outside any
`try`, so an exception unwound into the worker's generic row handler, which marked the
row Error **after** the replacement had already posted and without recording its name.

**The fix.** Resync gets its own lifecycle, deliberately outside the type switch:

```
validate → idempotency (tags _resync_of)
         → screen_resyncs()      refuse what cannot be replaced, before any write
         → the ordinary post loop, which knows nothing about resync
         → apply_supersessions()  cancel what was replaced, once everything has posted
```

Consequences worth stating: transfers, external transfers, loans and invoices all get
the behaviour for free; nothing is cancelled until the replacement provably exists; and
a closed period is refused while refusing is still free, rather than discovered after
the corrected figure is already in the ledger.

Supporting changes:

- `mark_changed_rows` propagates a tag across a transfer pair. Editing one leg's amount
  leaves the other leg's hash unchanged, so it would be skipped as a duplicate and the
  tagged leg stranded as `TRANSFER_PAIR_INCOMPLETE`. The pair is replaced as a unit.
- The reader emits `_window_reason` (`"created"` / `"modified"`), and idempotency Skips
  — not Errors, it is out of scope rather than broken — a modified-only row with no
  prior posting. This is the invariant the window change broke: *an import window may
  only create entries dated inside it.*
- Supersession is stored as **data**, not a status string: `superseded_by` and
  `supersedes` on `Cashew Import Row`. Reconcile verifies the successor is live; a
  cancelled document whose replacement has itself gone is reported as
  `supersession-broken`, which no status-string check could distinguish.
- A failed cancel after a successful repost is stamped `Supersede-Failed`, counted
  failed, and fails the run. It is the one outcome that leaves two live documents for
  one transaction and must never pass quietly.

Tests: `test_resync` 33/33, `test_sqlite_import` 9/9 (hash parity intact), `test_parser`
22/22, `test_integrity` 7/7. `test_mapping` (29/11/3) and `test_integration`'s setUpClass
`LinkValidationError` were baselined against a clean `git stash` and are identical —
pre-existing `work.local` fixture damage, not regressions.

## Verification

The `work.local` test runner cannot start — `DocType Department Approver not
found`, an HRMS leftover that fails identically on modules this work never
touched. Tests are written in `tests/test_integrity.py` for when it is repaired;
the assertions were executed directly against the site in the meantime, 9/9:

- same-currency foreign transfer with no rate errors both legs and posts nothing
- same-currency foreign transfer with a rate applies it (4.50 USD → 1,246.50 PKR)
- company-currency pair keeps the 1:1 path and stamps rate + base amount
- a new run built from a dict carrying another run's status, counters and
  timestamps comes out Draft and zeroed
- a reverted run with no rows claiming 54 posted is reported as drift
- a reverted run *with* rows keeps its lifetime `rows_posted` without drift
- `no_copy` present on every lifecycle field
- `revert_status` carries the two new external states
- `reconcile_run` and `audit_opening_balances` execute against real runs

`bench migrate` clean on `work.local`, all three patches recorded.

## Live pre-flight (read-only, 2026-08-07)

Run against `erp.nstack.xyz` over REST before deploying anything. No writes.
Script: `scratchpad/live_verify.py` (not committed — it reads credentials).

Permission sanity per the CLAUDE.md rule: 12 runs, 718 Journal Entries, 2,237 GL
Entries, 68 transfer rows — none of the lists are silently empty.

**Scope of the repost on live: exactly one entry**, the same one as `work.local`.
`ACC-JV-2026-00275`, 2026-05-14, 4.50 USD, booked 4.50 PKR (implied rate 1.0).
No other foreign same-currency transfer exists, and none are already at a real
rate, so nothing else is a candidate.

**Balance impact.** Every account-currency balance is untouched — the defect and
its repair live entirely in the company-currency column, and the replacement JE
balances the same way the original did. Only two PKR figures move, both toward
Cashew: Elevate Pay -1,238.85 → +10.38, and NSave's PKR side drops by the same
1,249.23 it was overstated by. That reproduces `work.local` exactly.

Balances at the last imported day (2026-07-30), live vs Cashew:

| Wallet → account | Cashew | ERP (account cur) | ERP (PKR) |
|---|---:|---:|---:|
| Saving → Saving | 454,695.00 | 454,695.00 | 454,695.00 |
| Emergency Fund → Meezan Bank | 181,181.41 | 181,181.41 | 181,181.41 |
| World First → World First | 160.00 | 160.00 | 44,645.24 |
| Elevate Pay → Elevate Pay | 0.00 | 0.00 | **-1,238.85** |
| NSave → NSave | 4,026.86 | **4,044.86** | 1,127,907.79 |
| Petty Cash → Petty Cash | 0.07 | **-1,323.93** | -1,323.93 |

### Blocker: the rate is not stored, so the result is not deterministic

Live holds exactly **one** Currency Exchange record — 2026-07-04 USD→PKR 277.0.
`_query_currency_exchange_table` only looks *backwards* from the posting date, so
for 2026-05-14 it finds nothing, the inverse lookup finds nothing, and
`_lookup_erp_rate` falls through to `_lookup_online_rate`. The posted rate would
then depend on the live server's outbound network and a 6-hour cache rather than
on stored data — and if egress is blocked the script prints SKIP and writes
nothing at all.

Fix before running it: create the Currency Exchange record the repost should use.

```
Currency Exchange: date 2026-05-14, USD → PKR, rate 278.60766133
```

That is the rate `work.local` resolved and posted at, so pinning it makes live
byte-identical rather than merely similar. With it in place the lookup never
reaches the network.

### Two gaps that are not ours

Both predate this work and neither is touched by any fix here.

- **NSave, 18.00 USD.** Localised to a single day: 2026-05-30/31, where Cashew
  says 813.00 and `ACC-JV-2026-00625` books 831.00. That entry carries no
  `run:` remark, so it is a manual Journal Entry, not an import — and 813→831
  is a digit transposition. Every other NSave day reconciles once the UTC
  date_created / posting_date off-by-one is netted out.
- **Petty Cash, 1,324.00 PKR.** Still unexplained; see above.

## Deploying to erp.nstack.xyz

Not done. In this order:

1. push, then `bench update --pull --apps cashew_integration`
2. `bench --site erp.nstack.xyz migrate` — runs the three backfill patches and adds
   `source_pk` / `source_modified`
3. create `Currency Exchange` 2026-05-14 USD→PKR **278.60766133** (see the blocker above)
4. `repost_same_currency_transfers` — dry run, then apply
5. **take a backup and restore it to work.local**, rehearse step 6 there first
6. `correct_stale_loan_je` — dry run must report exactly one entry, then apply
7. `bench build --app cashew_integration` for the SPA pill changes

Steps 4 and 6 both write GL and are independent of each other.
