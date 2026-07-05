# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable AGENTS.md plus every parent AGENTS.md above it

## Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:
- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

## User Preferences

When the user requests a durable behavior change, record it here or in the relevant child AGENTS.md

## Project Overview

**cashew_integration** is a Frappe v16 app that imports Cashew personal-finance exports (CSV and SQLite) into ERPNext as Sales Invoices, Purchase Invoices, and Journal Entries.

Key features:
- CSV import pipeline with full lifecycle (parse → validate → post → revert)
- SQLite import (f011): reads the Cashew SQLite DB directly via `importer/sqlite_reader.py`; add-alongside CSV, not a replacement
- Vue 3 SPA at `/cashew/` (Doppio-style, frappe-ui + Tailwind + ApexCharts)
- PWA-installable: dynamic manifest + scoped SW via `CashewPWAFile` page renderer
- Five icon surfaces: `/desk` Desktop Icon fixture, apps-screen, app_logo_url, SPA favicon, workspace sidebar lucide glyph

Architecture authority: `CLAUDE.md` (binding conventions) + `.fb/` (feature pipeline state). DOX is the editing rail — CLAUDE.md is the convention reference.

## Global Rules

- **SPA API discipline** (binding, all future SPA work): reads → `frappe.client.*`; link pickers → `<LinkField>`; writes → `api.py` whitelisted methods with `frappe.has_permission` guard; aggregates → one purpose-built endpoint per surface. See `CLAUDE.md` for full rules and rationale.
- **Build**: `bench build --app cashew_integration` (runs `yarn build` in `frontend/` via Doppio `build.json`). Commit `www/cashew.html`; gitignore `public/frontend/` and `frontend/node_modules`.
- **Linting / formatting**: `pre-commit run --all-files` runs ruff (sort + lint + format), prettier (JS/Vue), eslint (JS). Run before committing.
- **Tests**: `bench run-tests --app cashew_integration` (Python). SQLite import tests in `cashew_integration/tests/test_sqlite_import.py`.
- **Feature pipeline**: all architectural decisions must be logged in `.fb/` before implementation. Check `.fb/pipeline.yaml` and `.fb/features/index.yaml` before starting a feature.
- **Role gate for SPA**: `System Manager` OR `Accounts Manager`; no new role fixture.

## Child DOX Index

- [`cashew_integration/cashew_integration/AGENTS.md`](cashew_integration/cashew_integration/AGENTS.md) — Python Frappe app package: doctypes, API, hooks, fixtures, importer pipeline, tests
- [`frontend/AGENTS.md`](frontend/AGENTS.md) — Vue 3 SPA: components, routing, PWA build, design system
- [`.fb/AGENTS.md`](.fb/AGENTS.md) — BMad feature pipeline: feature registry, specs, arch decisions, reviews
