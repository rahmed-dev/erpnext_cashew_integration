# Import integrity verification — 2026-08-07

Method: read every posted document back from the live site over the REST API
(`https://erp.nstack.xyz`, user `ai@nstackhq.com`) and reconcile it against the
`Cashew Import Run` / `Cashew Import Row` records that claim to have created it.
Nothing was written; every call was a read.

Scripts used (scratchpad, not committed): `erp.py`, `verify.py`, `petty.py`.

## Scope

12 import runs, 5 live (`Completed`) and 7 `Reverted`:

| Run | Status | Source | Window | Rows | Posted |
|---|---|---|---|---|---|
| CASHEW-IMPORT-2026-000001 | Completed | CSV | 2026-03-05 .. 03-29 | 43 | 43 |
| CASHEW-IMPORT-2026-000005 | Completed | CSV | 2026-04-01 .. 04-30 | 54 | 54 |
| CASHEW-IMPORT-2026-000006 | Completed | CSV | 2026-05-02 .. 05-31 | 43 | 43 |
| CASHEW-IMPORT-2026-000013 | Completed | CSV | 2026-06-01 .. 06-30 | 75 | 75 |
| CASHEW-IMPORT-2026-000014 | Completed | SQLite | 2026-07-01 .. 07-30 | 95 | 95 |

276 Journal Entries referenced by live runs. Site totals: 718 JE, 8 PE, 2237 GL Entry.

## What is clean

- **Existence.** All 276 referenced Journal Entries exist. 0 missing, 0 draft.
- **Balance.** All 275 live JEs balance to the cent (debit == credit). 0 unbalanced.
- **Dates.** JE `posting_date` equals the source row's `txn_date` on every row. 0 drift.
- **Revert hygiene.** All 7 reverted runs left zero `posted_docname` values behind —
  no orphaned submitted document from a reverted run.
- **Transfer pairing.** 34 JEs are claimed by two rows each. Every one is a legitimate
  two-row transfer pair (`transfer_pair_row_idx` set on both legs). No accidental
  double-claiming.
- **Amounts.** Every JE's company-currency debit matches its source row amount, with
  one exception (finding 3).
- **No orphans.** 632 Journal Entries carry a `cashew_import_run` stamp. Every
  submitted one is claimed by a row — 0 documents the importer created but failed to
  record. This is the mirror of the row-side checks and the only way to catch a
  document that exists with nothing pointing at it.

## Findings

### 1. ~~Petty Cash is negative because no opening balances were ever imported~~ — WITHDRAWN

**This finding was wrong. The full Cashew SQLite export
(`cashew-2026-08-07-00-20-33-593933.sql`, 652 transactions, 2025-02-05 .. 2026-08-13)
settles it, and no opening balances are needed.**

The argument below reasoned from the real world: a physical cash account cannot run
to -132,313, so an opening balance must be missing. The source data does not agree.
Cashew's *own* running balance for the Petty Cash wallet reaches **-117,357.72 on
2026-01-01**, months before ERPNext knew the account existed. The wallet is used in a
way that goes deeply negative in Cashew too, so the dip proves nothing about ERPNext.

Per-wallet balance on 2026-03-04, the day before the import window, straight from
Cashew:

| Wallet | Balance on 2026-03-04 | First Cashew txn |
|---|---:|---|
| Petty Cash | **0.28** | 2025-07-18 |
| Saving | 214,695.00 | 2025-02-05 |
| NSave / Elevate Pay / World First / Emergency Fund | 0.00 | all after the cut |

Petty Cash opened at 0.28 — and ERPNext already holds exactly that, as the stray 0.28
on 2026-02-28 dismissed below as "not a Cashew document". Every other imported wallet
opened at zero. **Nothing is missing.** `importer/opening.py` stays in the app as a
general capability, but there is nothing to post for this company.

Reconciling ERPNext against Cashew over the actual import window instead (Cashew
balance on 2026-07-30, the last imported day) leaves two real gaps and four exact
matches:

| Wallet → ERP account | Cashew @ 2026-07-30 | ERPNext | Verdict |
|---|---:|---:|---|
| Saving → Saving - CS | 454,695.00 PKR | 454,695.00 | exact |
| Emergency Fund → Meezan Bank - CS | 181,181.41 PKR | 181,181.41 | exact |
| NSave → NSave - CS | 4,026.86 USD | 1,127,907.79 PKR | ~280.1 PKR/USD, consistent |
| Elevate Pay → Elevate Pay - CS | 0.00 USD | 0.00 USD / **-1,238.85 PKR** | finding 3 |
| Petty Cash → Petty Cash - CS | **0.07 PKR** | **-1,323.93 PKR** | gap of exactly **1,324.00** |

So the negative Petty Cash balance is a **1,324.00 PKR discrepancy**, not a six-figure
missing opening. Cause not yet identified.

This also reverses the reading of finding 2. Restoring the cancelled 13,750 expense
would move ERPNext *away* from Cashew (-15,073.93 against Cashew's 0.07), not toward
it. The cancellation looks deliberate and probably correct — most likely a duplicate.

<details>
<summary>Original (incorrect) finding, kept for the record</summary>


`Petty Cash - CS` closes at **-1,323.93 PKR** on 2026-07-30 across 217 GL entries
(debits 1,214,426.96 / credits 1,215,750.89).

This is not a posting defect. The ledger's first Cashew entry is 2026-03-05; the only
thing before it is a stray 0.28 on 2026-02-28 from `ACC-JV-2026-00035-1`, which is not
a Cashew document. Real petty cash on 2026-03-04 was not zero — whatever was in hand
that day was never carried into ERPNext.

The decisive evidence is that the running balance goes **deeply** negative mid-history,
which is impossible for physical cash:

| Account | Closing | Lowest running balance | On |
|---|---|---|---|
| Petty Cash - CS | -1,323.93 | **-132,313.22** | 2026-06-29 |
| NSave - CS | 1,127,907.79 | **-8,674.23** | 2026-03-14 |
| Cash / Saving / Meezan Bank | positive | never negative | — |

So the missing Petty Cash opening balance is at least ~132,313 PKR, and NSave is missing
at least ~8,674 (in company currency). Monthly net for Petty Cash: Mar +7,776,
Apr -4,031, May -3,595, Jun +12,594, Jul -14,068 — an ordinary spend/income pattern
sitting on a floor that starts too low.

**Fix:** post an Opening Entry JE dated the day before the first import (2026-03-04)
crediting `Temporary Opening - CS` and debiting each cash/bank account with its real
balance on that date. The app has no opening-balance mechanism; this is a one-time
manual entry, or a new feature if it should be part of the import flow.

</details>

### 2. `ACC-JV-2026-00042` is cancelled but a live run still points at it

`CASHEW-IMPORT-2026-000001` row 7 (2026-03-26, Petty Cash, PC Build, 13,750.00 PKR)
has `posted_docname = ACC-JV-2026-00042`, `validation_status = Valid`,
`revert_status` empty — but that JE is `docstatus = 2` (cancelled) and contributes no
GL. It was an expense (Petty Cash credit 13,750).

Two consequences:
- Petty Cash is currently **overstated by 13,750**. The honest figure for the imported
  data is **-15,073.93**, not -1,323.93. That makes finding 1 worse, not better.
- The row still reports itself as posted, so the app's own reconciliation would call
  this run clean. Nothing in the importer notices a document cancelled after the fact.

The revert flow itself is not at fault, and the evidence is unambiguous. The site holds
360 cancelled Journal Entries and they group cleanly by reverted run — 000002 (52),
000003 (52), 000009 (62), 000010 (62), 000011 (64), 000012 (64) — every one of those
runs having had its rows' `posted_docname` cleared, exactly as `_revert` is written to
do. `ACC-JV-2026-00042` is the single cancelled JE belonging to a run that was never
reverted. It was created at 07:13:45 and cancelled at 07:28:36, fifteen minutes later,
by Administrator.

So this was a manual Desk cancel. The gap is not in revert; it is that the importer
was **write-once** — it stamped `posted_docname` on a row and never looked at that
document again, so anything done to the document afterwards was invisible to it.

Decide whether to re-post the expense or clear the row's `posted_docname`.

### 3. Same-currency foreign transfers post at exchange rate 1.0

**Upgraded after deeper investigation — this is not cosmetic.** `Elevate Pay - CS`
closes at **-1,238.85 PKR** while being exactly **0.00 USD**. Its entire ledger is
three lines:

| Date | Voucher | USD | PKR |
|---|---|---:|---:|
| 2026-05-14 | ACC-JV-2026-00275 | +4.50 | **+4.50** |
| 2026-06-01 | ACC-JV-2026-00623 | -1.50 | -418.35 |
| 2026-06-01 | ACC-JV-2026-00624 | -3.00 | -825.00 |
| | | **0.00** | **-1,238.85** |

Money in was booked at rate 1.0; money out at the real rate. The account is
correct in its own currency and carries a permanent phantom loss in company
currency. Every rupee of Elevate Pay's negative balance comes from this one
defect.


`ACC-JV-2026-00275` (2026-05-14, NSave → Elevate Pay, 4.50 USD) posted as **4.50 PKR**
in company currency — both legs USD, `exchange_rate` 1.0, so a USD amount landed in a
PKR-denominated GL column unconverted. At ~277 PKR/USD it should be ~1,247.

This is a known-and-flagged gap, not a surprise: `importer/posting.py:132-140` takes the
`src_cur == dst_cur` branch and hardcodes `src_exr = dst_exr = 1.0`, with a comment that
says outright *"Assumes at least one leg is in company currency… If both legs are
foreign (e.g. USD→USD, company PKR) base amounts would be wrong; guard this path before
extending to that scenario."* The guard was never added.

Every other cross-currency transfer is correct — when one leg is PKR the rate is implied
from the counter-leg (e.g. `ACC-JV-2026-00604`: 902.70 USD → 250,002.77 PKR).

Impact today is small (4.50 vs ~1,247 PKR, and it shifts value between two USD accounts
rather than changing total assets) but the path will produce a large error on a large
same-currency transfer.

**Fix:** in the `src_cur == dst_cur` branch, when `src_cur != cmp_cur`, look up the
company-currency rate for that date (`_lookup_erp_rate`) and apply it to both legs
instead of 1.0. Error the row when no rate is available.

### 4. `exchange_rate` and `base_amount` are left at 0 on all Transfer rows

20 live rows have `raw_amount != 0` but `base_amount == 0` and `exchange_rate == 0` —
all of them USD `Transfer` rows. Cause: `mapping.py:202-203` skips
`txn_type == "Transfer"` entirely in `apply_exchange_rates()`, because posting derives
the implied rate per-leg later.

The GL is correct for these (see finding 3 for the one exception), but the row record
is not self-describing: anything reading `base_amount` off `Cashew Import Row` —
diagnostics, the SPA dashboard, any future reconciliation — undercounts transfers by
the full amount. Stamp the derived rate and base amount back onto the row after posting.

### 5. `CASHEW-IMPORT-2026-000004` is a phantom run created by Desk's Duplicate

`rows_total = 0`, `rows_valid = 0`, but `rows_posted = 54`, with zero child rows and
zero Journal Entries stamped with its name at any docstatus. It posted nothing.

Where the numbers came from is settled by the timestamps:

| Field | Run 000003 | Run 000004 |
|---|---|---|
| creation | 2026-05-03 10:17:39 | 2026-05-03 **10:24:51** |
| started_on | 2026-05-03 10:19:57.703577 | 2026-05-03 **10:19:57.703577** |
| finished_on | 2026-05-03 10:24:44.117775 | 2026-05-03 **10:24:44.117775** |
| source_file | cashew-2026-05-03-06-31-00-370944.csv | *same file* |

Run 000004 reports having started and finished **before it was created**, with
timestamps identical to run 000003 down to the microsecond. It is a duplicate of
000003: `Cashew Import Run` had `no_copy` on no field at all, so Desk's Duplicate
carried across status, counters and lifecycle timestamps verbatim.

Harmless here because it owns nothing, but the same mechanism could produce a run
that looks Completed and blocks deletion while owning no documents.

### 6. Calendar gaps between import windows

Coverage is 2026-03-05 .. 2026-07-30 with three edges worth confirming against Cashew:

- Nothing before **2026-03-05** (see finding 1).
- May starts **2026-05-02** — no 2026-05-01 row.
- July ends **2026-07-30** — no 2026-07-31 row.

These may simply be days with no transactions. Confirm in the Cashew app before
treating them as data loss; if a day is missing, re-import that window.

## Priority

1. Finding 1 — opening balances. Everything downstream (dashboard balance tiles, any
   cash reporting) is wrong until this exists.
2. Finding 2 — the cancelled JE, and the importer's blindness to post-hoc cancellation.
3. Finding 3 — the same-currency FX branch, before a large USD→USD transfer hits it.
4. Findings 4–6 — fidelity and hygiene.
