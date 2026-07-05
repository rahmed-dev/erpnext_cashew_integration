# BMad Feature Pipeline

## Purpose

Authoritative state for all features built under the BMad Frappe Builder pipeline. Contains architecture decisions, feature specs, build reviews, and the pipeline stage tracker.

## Ownership

- `pipeline.yaml` — current pipeline stage and handoff state
- `features/index.yaml` — feature registry (all fNNN entries)
- `system-arch/` — system-wide architecture decisions that span features
- `features/{fid}-{name}/` — per-feature folder; each contains `feature.yaml` plus any of: `specs/`, `arch/`, `reviews/`

## Local Contracts

- **Check before building**: read `pipeline.yaml` and `features/index.yaml` before starting any feature work. The Orch gate controls what is in-flight.
- **Log decisions first**: any architectural decision must be recorded in `arch/decisions.md` (feature-scoped) or `system-arch/` (cross-feature) before implementation begins.
- **Spec files**: `{cid}-spec.md` is the implementation contract; `{cid}-story.md` is optional background (skip in TD per project preference).
- **Review findings**: `reviews/c{NNN}-findings.md` records code-review output per cycle; do not delete after fixing — they are the audit trail.
- **feature.yaml status field** is the single source of truth for a feature's lifecycle state; do not infer state from the presence or absence of other files.

## Work Guidance

- Feature IDs are assigned sequentially (`f001`, `f002`, …); do not reuse or skip.
- When a feature is done, mark `feature.yaml` status = `done` and record the completion date.
- Parked decisions go in `arch/parked.md` (not deleted); rejected decisions go in `arch/decisions.md` with a REJECTED label and rationale.
- Do not place implementation code, migration scripts, or test data inside `.fb/` — it is docs-only.

## Verification

No automated check. Manually verify: `features/index.yaml` lists every `fNNN` folder present; `pipeline.yaml` matches the current handoff state.
