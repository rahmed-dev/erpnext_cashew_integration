# c001 — spa-scaffold

> **Type:** build-tooling
> **Depends on:** (none — entry point of the feature)
> **Arch refs:** D1 (Doppio CLI + frappe-ui), D2 (HTML5 history host shape),
> D4 (build hook — covered by c003), D6 (state mgmt — resolved here),
> D13 Amendment 1 (CSS vars for theming)

---

## Overview

Run Doppio's `bench add-frontend` to scaffold the Vue 3 SPA inside
`cashew_integration/`. Doppio produces 90% of the boilerplate (vue, vue-router,
frappe-ui, vite + plugins, tailwind preset, `src/` skeleton, build hook,
placeholder `www/<app>.html`). This component captures **the Doppio
invocation answers** + the **small TD overlay** applied on top (extra deps,
no-Pinia binding, root-level gitignore, CSS-var defaults).

The component does NOT include the boot-dict / perm gate / hooks.py edits
(c002), the build-hook verification + dev loop docs (c003), the router
config beyond the Doppio placeholder (c004), or any page SFCs (c005+).

---

## Doppio invocation

Command: `bench add-frontend --app cashew_integration`

Interactive answers:

| Prompt | Answer | Why |
|---|---|---|
| Frontend framework | **Vue** | D1 |
| Frontend folder name | **frontend** | Matches Frappe CRM / Helpdesk convention. |
| TypeScript? | **No** | Matches frappe-ui examples + Frappe CRM. JS keeps friction low; we lose compile-time type-check but gain template ergonomics. |
| Use frappe-ui? | **Yes** | D1. |
| Router type | **history** (HTML5) | D2. |
| App name (entry HTML) | **cashew** | Produces `www/cashew.html` (consumed by c002). |
| Add Tailwind? | **Yes** (frappe-ui's preset) | Design handoff DESIGN_TOKENS expects Tailwind. |
| Set up build hook? | **Yes** | c003 verifies. |
| Enable lucideIcons in vite plugin? | **Yes** | DESIGN_TOKENS + COMPONENT_MAPPING reference lucide icons. |

> If Doppio's prompts diverge from this list on the installed version, Dev
> reconciles with intent (Vue + HTML5 history + frappe-ui + Tailwind +
> Lucide). Spec captures intent, not exact prompt strings.

---

## TD overlay (deltas applied after Doppio runs)

### Extra deps
```bash
cd frontend
yarn add socket.io-client@^4.7
yarn add lucide-vue-next
```
- `socket.io-client` — needed by c008 (D8 realtime).
- `lucide-vue-next` — Vue wrapper for lucide icons. Doppio enables `lucideIcons: true` in the vite plugin (auto-import), but the Vue wrapper package may still need explicit install depending on Doppio version.

### Forbidden deps (D6 binding)
- **No** `pinia`.
- **No** `pinia-plugin-persistedstate`.
- **No** other state-persistence library.
- **No** `localStorage` / `sessionStorage` writes anywhere in `src/`.

If `pinia` lands in `package.json`, remove it. Cashew SPA state pattern is
explicitly frappe-ui resources + composables (see "State pattern" below).

### `cashew_integration/.gitignore` (app-root, not the one inside `frontend/`)
Append (Doppio handles the inside-`frontend/` gitignore; not this outer one):
```
frontend/node_modules
frontend/dist
public/frontend/
```

### `frontend/src/index.css`
Append (or create if Doppio's template doesn't include `:root` block):
```css
:root {
  --cs-accent:     #4f46e5;
  --cs-accent-700: #4338ca;
  --cs-accent-100: #e0e7ff;
  --cs-accent-50:  #eef2ff;
}
```
Indigo defaults so first paint is sane before c002's boot dict + c004's
shell apply the user's actual preset.

### `frontend/vite.config.js` — confirm
After Doppio writes the file, verify the `frappeui()` plugin call has:
```js
frappeui({
  frappeProxy: true,
  jinjaBootData: true,
  lucideIcons: true,
  // buildConfig: { outDir, emptyOutDir, sourcemap } — Doppio sets these
})
```
If `lucideIcons: true` is missing, add it. Other flags should already be
set by Doppio's defaults.

---

## State pattern (D6 resolved)

**Pick:** frappe-ui `createResource` for data, tiny composables for derived
shared state.

**Rationale:**
- `createResource` is already a frappe-ui primitive (no extra dep).
- Caching, loading/error state, refetch all built-in.
- Method parameter maps directly to the four D5 API rules:
  - `frappe.client.get_list` for read lists
  - `frappe.client.get_doc` for read singles
  - `frappe.client.set_value` for inline writes
  - `cashew_integration.api.<method>` for whitelisted writes + `dashboard_summary`
- Matches the Frappe CRM + Helpdesk pattern (which D2 already mirrored for
  host shape).
- Avoids Pinia + the persistence temptation (D6 forbids).

**Conventions:**

- One file per logical resource in `src/api/`:
  ```js
  // src/api/useImportRuns.js
  import { createResource } from 'frappe-ui';

  export const useImportRunsList = (filters = {}) =>
    createResource({
      method: 'frappe.client.get_list',
      params: {
        doctype: 'Cashew Import Run',
        fields: ['name', 'status', 'period_start', 'period_end', 'company'],
        filters,
        order_by: 'modified desc',
        limit: 50,
      },
      cache: ['cashew-import-runs', filters],
      auto: true,
    });

  export const useImportRun = (runName) =>
    createResource({
      method: 'frappe.client.get_doc',
      params: { doctype: 'Cashew Import Run', name: runName },
      cache: ['cashew-import-run', runName],
      auto: true,
    });
  ```
- Cross-component shared state (current period selection, current run name,
  dirty flag) in module-scope composables exporting a `ref` + helpers:
  ```js
  // src/state/useDashboardPeriod.js
  import { ref } from 'vue';
  const period = ref({ start: null, end: null });   // session-only
  export const useDashboardPeriod = () => ({ period, setPeriod: p => period.value = p });
  ```
- **No initialization from `localStorage`.** State resets on every fresh
  page load. D6 binding.

---

## `src/` layout after scaffold + overlay

Doppio populates most of this. Files marked **(TD-added)** are c001's
overlay; everything else is Doppio default and may be edited by later
components.

```
frontend/
├── package.json                  # Doppio + 2 extra deps
├── yarn.lock
├── vite.config.js                # Doppio; lucideIcons confirmed true
├── index.html                    # Doppio
├── tailwind.config.js            # Doppio (frappe-ui preset)
├── postcss.config.js             # Doppio
├── .gitignore                    # Doppio
└── src/
    ├── main.js                   # Doppio; c004 adds ThemeController.init()
    ├── App.vue                   # Doppio placeholder; c004 fills shell
    ├── router.js                 # Doppio placeholder; c004 fills routes
    ├── index.css                 # Doppio + TD :root block (CSS vars)
    ├── api/                      # (TD-added empty dir) populated by c005+
    │   └── .gitkeep
    ├── state/                    # (TD-added empty dir) populated by c004+
    │   └── .gitkeep
    ├── components/               # populated by c004+
    └── pages/                    # populated by c005/c006/c007/c012
```

---

## TD calls made inside arch envelope (not surfaced)

These are TD decisions inside D1's "Doppio + frappe-ui" envelope. Listed
for traceability; no separate sign-off requested.

- **JavaScript, not TypeScript** — match frappe-ui examples + CRM.
- **Vite 5** (whatever Doppio + bench-16's frappe-ui pin to) — not Vite 6.
- **Vue 3.4+** (frappe-ui peer dep) — not 3.5 until frappe-ui's peer moves.
- **Tailwind 3.4** (frappe-ui's preset is on 3.x) — not 4.
- **lucide-vue-next** for the Vue wrapper — not `lucide` (the raw package).
- **No Vitest, no Storybook in c001.** If unit tests are wanted later, add
  a follow-up component spec. Out of scope for "scaffold".

---

## Acceptance

- [ ] `bench add-frontend --app cashew_integration` runs successfully with
      the answers above.
- [ ] `frontend/` directory exists at `cashew_integration/frontend/`.
- [ ] `cd frontend && yarn install` completes without error.
- [ ] `yarn dev` launches Vite (typically port 8080) and serves a
      placeholder page proving Vue + router boot.
- [ ] `package.json` includes `vue`, `vue-router`, `frappe-ui`,
      `socket.io-client`, `lucide-vue-next`.
- [ ] `package.json` does NOT include `pinia` or any `*persistedstate*`.
- [ ] `grep -r "localStorage\|sessionStorage" frontend/src/` returns no
      hits.
- [ ] `cashew_integration/.gitignore` contains `frontend/node_modules`,
      `frontend/dist`, `public/frontend/`.
- [ ] `frontend/src/index.css` has the `:root` block with the 4
      `--cs-accent*` properties.
- [ ] `frontend/vite.config.js` has `lucideIcons: true` in the `frappeui()`
      plugin call.
- [ ] `yarn build` produces `cashew_integration/public/frontend/index.html`
      + assets directory. (Same artifact c003 + c002 consume.)

---

## Open items (handed off)

- Boot dict shape (csrf, session, sysdefaults, accent fields, etc.) → c002.
- Build hook verification + dev loop docs → c003.
- Router routes (`/`, `/runs`, `/runs/new`, `/runs/:run_name`, `/settings`)
  + Shell layout → c004.
- `theme.js` PRESET_TABLE + `deriveShades(hex)` HSL function body → c004
  (depends on c013 Amendment 1).
- Page SFCs → c005 / c006 / c007 / c012.
- API composables in `src/api/` → c005 / c006 / c007 / c012 (each adds
  what it needs).
