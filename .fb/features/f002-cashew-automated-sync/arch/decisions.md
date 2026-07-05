# f002 — Cashew Automated Sync (Google Drive transport)

Revived 2026-06-27. Original f002 was cancelled because Cashew exposes no API.
This revives the same goal — sync without manual local upload — using Cashew's
Google Drive export as the transport. One feature area, one decision at a time.

## Auto-Sync via Google Drive — REJECTED — 2026-06-27
**Decision:** Do NOT attempt to read Cashew's continuous **Sync** backup from
Google Drive.
**Rationale:** Cashew's Sync feature writes to Drive's hidden `appDataFolder`,
which is readable **only by the app that wrote it**. No service account, no user
OAuth through a different client can ever be granted access. The originally
imagined "ERPNext auto-pulls the live Cashew sync" is technically impossible.
Confirmed with user: their backup is the Sync (hidden-folder) feature.

## Transport: Manual Monthly Export + Drive File Picker — 2026-06-27
**Decision:** User performs a periodic (≈monthly) **manual export** from Cashew
to a *visible* Google Drive folder. ERPNext provides a file-picker UI that lists
files in that folder; the user selects which file to import this run.
**Rationale:** The visible export is the only Cashew artifact ERPNext can
reach. A human-in-the-loop monthly cadence matches personal-finance usage and
avoids the impossible auto-sync. The Drive picker is ergonomic for mobile users
(Cashew export → Drive → ERPNext) versus shuttling files off a phone manually.

## Export Format: CSV (Path A) — 2026-06-27 — ⚠️ SUPERSEDED by D8 (2026-06-27)
**Decision:** The monthly export is the **CSV export** (not the full .sql/.sqlite
backup).
**Rationale:** CSV lets us reuse the *entire* f001 pipeline unchanged
(parse → validate → preview → post → revert → period detection). The full-backup
(stable-ID) path was considered and reserved for the edit/delete case below, but
is not needed here.
**SUPERSEDED:** Scanned the user's actual export — it is the **full SQLite DB**,
not CSV. See D8. Path B adopted.

## Idempotency: Reuse f001 Content-Hash — 2026-06-27 — ⚠️ SUPERSEDED by D9 (2026-06-27)
**Decision:** Dedupe reuses f001's existing content-hash external-ID mechanism
(`importer/idempotency.py`). The 2026-04-08 system-arch "Idempotency and
Duplicate Handling" decision stands unchanged — no cascade.
**Rationale:** User confirmed they treat closed months as **append-only** — they
do not edit or delete past transactions in Cashew after the fact. Therefore the
content-hash's known weakness (an edited row re-hashes and looks new → duplicate)
does not apply. Re-importing an overlapping monthly export simply re-skips
already-posted rows by hash.
**Reserved upgrade path (NOT built):** if append-only ever stops holding, switch
the source to the full backup DB (Cashew's stable primary key / UUID per
transaction). Stable IDs survive edits, turning "edited row" into a reconcilable
update instead of a duplicate, and would future-proof f008 reconciliation. This
is a deliberate fork left open, not current scope.
**SUPERSEDED:** The reserved upgrade is now the chosen path — see D9. The export
in hand IS the stable-ID backup, so content-hash is no longer needed.

## Drive Access: Service Account (lean) — 2026-06-27
**Decision:** ERPNext authenticates to Google Drive with a **service account**;
the user shares the Cashew export folder with the service account's email.
**Rationale:** User asked for advice. Service account = no per-run consent screen
and no token expiry. The OAuth-on-personal-login alternative was rejected:
Drive is a sensitive scope, so an unverified ("testing") OAuth app has its
refresh token expire after ~7 days — which would force re-authorization between
nearly every monthly sync. Service-account folder-sharing avoids that entirely.
A Google Cloud project + service account is free.

## Reuse Seam: confirmed — 2026-06-27 — ⚠️ REFINED by D10 (2026-06-27)
**Decision:** Implement Drive transport as a thin **source adapter** that fetches
the selected CSV's bytes into the existing `Cashew Import Run` file input, then
hands off to the unchanged `importer/worker.py` orchestration.
**Rationale:** Code audit confirmed f001 already separates concerns —
`parser.py` (parse) is decoupled from `posting.py` (post), with `worker.py`
orchestrating and `idempotency.py` deduping. The seam f002's stub promised
("keep f001 boundaries clean so transport can swap") genuinely exists, so the new
code is limited to: Drive auth, folder listing, file fetch, and the picker UI.

## Direction: One-way Cashew → ERPNext — 2026-06-27
**Decision:** Sync is strictly one-way. Cashew remains source of truth for raw
transactions; ERPNext only ingests. No write-back to Cashew.
**Rationale:** Two-way would require conflict resolution for no real benefit in a
personal-finance, single-user context.

---

# 2026-06-27 — Path B adopted (export scanned, decisions revised)

Scanned the user's actual file `cashew-2026-06-27-05-22-48-840261.sql`. Despite
the `.sql` extension it is a **binary SQLite 3 database** — Cashew's full backup.
User confirmed: this is a **manual full-DB export** they will perform monthly to
Drive (not a CSV, not the hidden Sync folder). Scan facts (this file):
534 transactions (all `paid=1`), 7 wallets (pkr/usd), 55 categories, 1277
`delete_logs`. Key columns: `transaction_pk` (UUID), `income` 0/1,
`paired_transaction_fk`, `wallet_fk`→`wallets.currency`, `date_time_modified`.

## D8 — Export Format: full SQLite DB (Path B) — 2026-06-27
**Supersedes D3 (CSV).**
**Decision:** Transport artifact is Cashew's **full SQLite backup** (`.sql` /
`.sqlite`). The monthly Drive export is this DB, exported manually.
**Rationale:** It is the file the user actually has and will keep exporting. It
carries everything the CSV lacked — stable IDs, an explicit income flag, paired
transfer legs, per-wallet currency. Strictly more information than CSV at no extra
user effort (same "export to Drive" gesture).
**Adapter step:** new SQLite read (Python stdlib `sqlite3`, no new dependency) →
rows shaped to what `worker.py`/`posting.py` already expect.

## D9 — Idempotency: stable `transaction_pk`, insert-only — 2026-06-27
**Supersedes D4 (content-hash) + closes the reserved upgrade.**
**Decision:** Dedupe on Cashew's `transaction_pk` (UUID) as the external ID.
**Insert-only**: new pks are posted; already-seen pks are skipped. Edits and
deletes are **NOT** propagated this round (see D11).
**Rationale:** Stable IDs remove the content-hash's append-only assumption and its
edited-row-duplicates failure mode entirely. User chose the lean insert-only
scope. No system-arch idempotency revision is forced — this is a per-feature
external-ID choice; f001's content-hash mechanism stays as-is for the CSV path.

## D10 — Adapter weight: a real SQLite parser variant (refines D6) — 2026-06-27
**Decision:** The Drive source adapter is **not** "thin." It is a new parser
variant that: opens the SQLite DB, reads `transactions`, resolves `category_fk`/
`wallet_fk` → **names** by joining `categories.name` / `wallets.name`, derives
direction from the `income` flag, and handles transfer pairs.
**Still reused unchanged:** `posting.py`, `worker.py`, `Cashew Import Run`,
period detection, revert, service-account Drive auth, the file-picker UI.
**FK→name reuse:** because it resolves to names, the **existing name-based Cashew
Category Mapping / Account Mapping doctypes are reused with no rework**. (Sentinel
`category_fk='0'` / `wallet_fk='0'`=Investment handled specially — see D11.)

## D11 — Open items carried to TD — 2026-06-27
1. **Cross-path dedup hazard.** f001 CSV writes content-hash external IDs; f002
   writes `transaction_pk`. The *same* real transaction imported via both paths
   would NOT share an external ID → double-post. **Rule:** f002 (SQLite) is the
   go-forward path; do not run both for overlapping periods. TD to decide whether
   to actively block/migrate f001-era content-hash rows or just document the rule.
2. **Transfer model is not purely paired.** 61 rows at `category_fk='0'` but only
   29 carry `paired_transaction_fk`. The adapter must handle unpaired transfer-
   category rows too (map to the existing Balance Correction / transfer handling),
   not assume the pair pointer covers all transfers.
3. **Filter to real postings.** Only `paid=1` rows are actual transactions; the DB
   also holds recurring/upcoming templates (481 rows carry `reoccurrence`). Adapter
   must import only settled rows. (In this sample all 534 are `paid=1`, but the
   filter is required for future exports.)
4. **Reserved (NOT now): edit + delete propagation.** `date_time_modified` and
   `delete_logs` make it possible to update/reverse posted GL later. Deferred —
   reversing posted SI/PI/Payment Entries is a separate project. Stable IDs (D9)
   leave this door open for free.
5. **Folder pointer.** How ERPNext points at the Drive export folder (folder ID in
   Cashew Settings vs. configurable per run) — unchanged open item from the picker.
