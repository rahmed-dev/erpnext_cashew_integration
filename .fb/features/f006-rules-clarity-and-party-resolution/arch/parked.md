# f006 — Parked Ideas (Out of Scope)

Captured during architect pass for future feature consideration. Not part of f006 component breakdown.

---

## P1 — Prefill Party From Prior Import

**Source:** User raised 2026-05-03 during Decision 2 discussion when asked about run-level default party.

**Idea:** When a new Cashew Import Row matches a posted row from a prior Import Run on (category, raw_account, similar amount? text similarity?), suggest or auto-fill the party that was used last time. Reduces manual party entry on recurring transactions (e.g. monthly rent payment, recurring salary).

**Why parked:**
- Needs its own architecture pass — similarity heuristic (exact match vs fuzzy?), confidence scoring, suggest-vs-autofill UX, audit (which prior row inspired this?), opt-in toggle.
- Adds a separate "learning" subsystem on top of the simple manual-set model just locked in Decision 2.
- Not blocking — Vue Row Explorer (Decision 3) bulk-set already covers the same recurring-transaction pain via "select all matching, set party" in two clicks.

**Promote to feature when:** user reports manual party set is the bottleneck even after Vue Explorer ships, OR appetite for a smarter suggestion engine.

---

## P2 — Mapping Fixtures (Starter Categories + Accounts)

**Source:** Architect scan, 2026-05-03 (`opportunities.md` D2).

**Idea:** Ship starter Cashew Category Mapping + Cashew Account Mapping fixtures so a fresh install isn't blank. Could include common Cashew default categories (Salary, Rent, Loan Payment Received, Lent, etc.) with sensible category_type assignments.

**Why parked:** Onboarding nice-to-have, not f006 scope. Touches install / fixtures pipeline. Worth a small follow-up feature.

---

## P3 — System-Arch `data-flow.md` Wording Refresh

**Source:** Decision 2 cascade analysis.

**Action needed (post-f006-dev):** Update `data-flow.md` "Per-Row Party Resolution (No CSV Editing) — 2026-04-08" wording. The pipeline `mapping rules → text extraction → preview override` collapses to **per-row manual set only** for f006 onward. Add a note that pre-f006 Income/Expense path retains the old wording for backwards-compat docs.

**Why parked:** Pure documentation update. Schedule when f006 dev work completes — wording must match what shipped, not what was planned.
