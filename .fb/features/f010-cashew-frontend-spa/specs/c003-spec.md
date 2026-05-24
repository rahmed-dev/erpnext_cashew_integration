# c003 — build-hook

> **Type:** build-tooling
> **Depends on:** c001 (frontend scaffold), c002 (www/cashew.* present)
> **Arch refs:** D4 (build pipeline via `bench build` hook; commit
> `cashew.html`, gitignore `public/frontend/`)

---

## Overview

Verify Doppio's build hook + document the dev loop. Most mechanical work
is Doppio's; this spec captures the **contract** (`bench build` runs
`yarn install --check-files && yarn build`, output lands at correct paths,
gitignore policy enforced) and adds a `frontend/README.md` so future devs
and agents know how to run the SPA locally.

Resolves S1 = A (docs in `frontend/README.md`), S2 = A (`yarn install
--check-files` on every `bench build`).

---

## Build hook (Doppio-scaffolded, TD verifies)

Doppio's installed version writes one of two shapes. Dev verifies which is
present and confirms the command list matches:

**Shape A — `cashew_integration/build.json`:**
```json
{
  "cashew": [
    "yarn --cwd frontend install --check-files",
    "yarn --cwd frontend build"
  ]
}
```

**Shape B — `cashew_integration/hooks.py build_command`:**
```python
build_command = [
    "yarn --cwd frontend install --check-files",
    "yarn --cwd frontend build",
]
```

Both achieve the same outcome: `bench build --app cashew_integration` runs
the install + build steps. Doppio's recent versions prefer Shape A.

**TD requirement (regardless of shape):**
- `yarn install --check-files` must run before `yarn build`. Idempotent;
  fast when `yarn.lock` unchanged; correct on fresh checkout.
- No source maps in production (`vite.config.js: build.sourcemap: false`,
  set in c001).

---

## Output paths (D4 contract)

`yarn build` (via vite + Doppio frappe-ui plugin) produces:

```
cashew_integration/public/frontend/
├── index.html                         # vite's entry HTML — used by the copy step below
├── assets/
│   ├── index-<hash>.js                # main bundle
│   ├── index-<hash>.css               # styles
│   └── <other hashed assets>
```

Plus a post-build step that copies `public/frontend/index.html` to
`www/cashew.html` (committed). This is handled by **one** of:

1. **frappe-ui vite plugin's `emitIndexHtmlTo` option** (preferred —
   portable, no shell needed):
   ```js
   frappeui({
     ...
     buildConfig: {
       outDir: '../cashew_integration/public/frontend',
       emitIndexHtmlTo: '../cashew_integration/www/cashew.html',
     },
   })
   ```
2. **An npm script step** (fallback if the plugin lacks the option):
   ```json
   "scripts": {
     "build": "vite build && node -e \"require('fs').copyFileSync('../cashew_integration/public/frontend/index.html', '../cashew_integration/www/cashew.html')\""
   }
   ```
   (Node one-liner instead of `cp` — works on Windows + macOS + Linux.)

Dev picks the right one based on Doppio's installed version. The contract
is: after `bench build`, `www/cashew.html` reflects the latest bundle
hashes.

---

## Commit / gitignore policy (D4 enforced)

**Committed to git:**
- `cashew_integration/www/cashew.html` — build artifact, **but committed**
  per D4 so a fresh `bench install-app cashew_integration` serves
  `/cashew` immediately without a build step.
- `cashew_integration/public/images/cashew-app-icon.svg` — static asset
  (c002).
- `cashew_integration/frontend/` source tree (except `node_modules` +
  `dist`).

**Gitignored:** (entries added by c001 to `cashew_integration/.gitignore`)
- `frontend/node_modules`
- `frontend/dist`
- `public/frontend/`

Verify these entries are present (c001 acceptance covers it; restated
here as the c003 contract).

**Why `www/cashew.html` is committed despite being build output:**
- Fresh `bench install-app cashew_integration` does NOT run `bench build`.
- Without the committed shell, `/cashew` 404s on first deploy until
  someone runs build.
- Hashes inside the file change rarely (only when source changes); diff
  noise is minimal.

**Why `public/frontend/` is gitignored:**
- Content-hashed; every build regenerates filenames.
- Bloats git history fast (megabytes per build).
- CI / deploy runs `bench build` after pull — no production gap.

---

## `frontend/README.md`

Create the file. Content:

```markdown
# Cashew SPA — frontend

Vue 3 SPA bundled into the `cashew_integration` Frappe app. Served at
`/cashew` via the `www/cashew.*` route.

See `cashew_integration/CLAUDE.md` for architecture and API discipline.

## First-time setup

```bash
cd frontend
yarn install
```

## Two-terminal dev loop

**Terminal 1 — bench backend:**
```bash
bench start
```
Frappe at http://127.0.0.1:8000 (site `work.local`).

**Terminal 2 — vite dev server:**
```bash
cd frontend
yarn dev
```
Opens http://127.0.0.1:8080. API calls + the `window.boot` payload proxy
through to bench. Vue, CSS, and composables HMR.

**Open the SPA at:** http://127.0.0.1:8080/cashew

> The path matters. http://127.0.0.1:8080/ has no boot dict — frappe-ui's
> vite plugin pulls `window.boot` from `/cashew` via Jinja proxy to
> bench.

## Production build

```bash
bench build --app cashew_integration
```

Runs `yarn install --check-files && yarn build`. Output:
- `cashew_integration/public/frontend/<hashed assets>` — content-hashed
  bundles (gitignored)
- `cashew_integration/www/cashew.html` — shell with hash references
  (committed)

CI/deploy uses the same command via `bench update`.

## State management

`frappe-ui` `createResource` for data fetching. Module-scope composables
for session-only shared state. **No Pinia. No `localStorage`. No
`sessionStorage`.** This is binding — see arch decision D6.

## Common pitfalls

- **`window.boot` is undefined** — you're on `/` instead of `/cashew`,
  or bench isn't running.
- **CSRF errors on writes** — `frappe-ui`'s axios needs
  `X-Frappe-CSRF-Token: window.boot.csrf_token` in default headers.
  Confirm `src/main.js` sets it.
- **Stale boot after editing Cashew Settings** — boot is read once at
  page load. Realtime (c008) propagates Cashew Settings changes
  in-session; a full reload picks up other edits.
- **Build fails with cryptic module resolution errors** — delete
  `frontend/node_modules` + `frontend/yarn.lock`, then `yarn install`.
  Usually a Doppio + frappe-ui peer-version drift.
- **`yarn dev` 404s on `/cashew`** — bench isn't running on :8000.
  Start `bench start` in another terminal.

## Tests

None yet. If unit / e2e tests are added, document the runner here.

## Files of note

- `vite.config.js` — Doppio + frappe-ui plugin config; `lucideIcons: true`
  is required.
- `src/main.js` — Vue + router + frappe-ui plugin init.
- `src/boot.js` — `window.boot` accessor + has_perm helpers.
- `src/theme.js` — preset → CSS-var table + `deriveShades(hex)` for the
  Custom accent path (c013 Amendment 1).
- `src/index.css` — Tailwind directives + default `--cs-accent*` vars.

## Architecture references

All under `cashew_integration/.fb/features/f010-cashew-frontend-spa/`:
- `arch/decisions.md` — D1-D14 system architecture
- `arch/decisions-b.md` — amendments (D13/D14 Amendment 1)
- `specs/` — per-component implementation specs
- `design_handoff_f010_cashew_spa/` — visual reference (prototype,
  tokens, interactions)
```

---

## Cross-link in `cashew_integration/CLAUDE.md`

Append one line to the existing SPA hosting section:

```markdown
**Local dev loop:** see `frontend/README.md`.
```

Place after the "Build:" bullet, before "PWA on." line. Keeps CLAUDE.md
focused on architecture; lets implementation detail live where Dev looks.

---

## Files touched by Dev

```
cashew_integration/build.json              # NEW or VERIFY (Doppio scaffold; Shape A or B)
cashew_integration/hooks.py                # POSSIBLE EDIT (Shape B only)
cashew_integration/frontend/vite.config.js # VERIFY emitIndexHtmlTo (or add npm-script fallback)
cashew_integration/frontend/package.json   # VERIFY build script (Shape 2 fallback)
cashew_integration/frontend/README.md      # NEW
cashew_integration/CLAUDE.md               # EDIT — add one-line cross-link
```

No new Python, no new JS source. Pure tooling + docs.

---

## Acceptance

- [ ] `bench build --app cashew_integration` completes without error from
      a clean state (`rm -rf frontend/node_modules` first, then run).
- [ ] After a successful build:
      - `cashew_integration/public/frontend/index.html` exists
      - `cashew_integration/public/frontend/assets/index-<hash>.js` exists
      - `cashew_integration/www/cashew.html` is updated and references
        the same hash
- [ ] Running `bench build` twice in a row with no source change produces
      no diff in either file (idempotency).
- [ ] In two-terminal dev:
      - http://127.0.0.1:8080/cashew renders the SPA shell
      - editing `frontend/src/index.css` triggers HMR (CSS swaps without
        full reload)
      - editing a `.vue` file under `frontend/src/pages/` triggers HMR
        (component re-renders without full reload)
      - Network tab shows API calls to `/api/method/...` returning 200
- [ ] After `bench build`, `git status` shows only `www/cashew.html`
      modified (when bundle hash actually changed) — never any file under
      `public/frontend/`.
- [ ] `frontend/README.md` exists with the dev loop docs above.
- [ ] `cashew_integration/CLAUDE.md` has the one-line cross-link to the
      README.

---

## TD calls inside arch envelope (not surfacing)

- `yarn` not `npm`. Doppio default; lockfile is `yarn.lock`.
- `yarn install --check-files` flag — idempotent + cheap (~3s when
  unchanged). Picked over `--frozen-lockfile` so devs can update deps
  without a workflow tweak.
- Production build emits no source maps (`build.sourcemap: false`,
  set in c001). Bundle size > debuggability for an operator tool;
  revisit if Sentry-style remote debugging gets adopted.
- The `node -e "require('fs').copyFileSync(...)"` fallback over `cp`:
  portable across OSes without adding a `cross-env`-style dep.

---

## Open items (handed off)

- CI integration (`bench build` in deploy pipeline) — out of f010 scope;
  assumed handled by existing deploy automation (Frappe Cloud or self-host
  bench update).
- Bundle-size dashboarding (`vite-bundle-visualizer`, source-map-explorer) —
  nice-to-have; defer until bundle bloat becomes a real complaint.
- Lighthouse + accessibility CI — out of scope; future audit feature.
