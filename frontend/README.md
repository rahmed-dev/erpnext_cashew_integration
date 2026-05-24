# Cashew SPA (f010)

Vue 3 + Vite + frappe-ui + Tailwind frontend for the Cashew Integration app.
Mounts at **`/frontend`** on the Frappe site.

## Quick reference

| Concern | Where |
|---|---|
| Web entry / boot dict | `cashew_integration/cashew_integration/www/frontend.py` |
| Built HTML shell (committed) | `cashew_integration/cashew_integration/www/frontend.html` |
| Built assets (gitignored) | `cashew_integration/cashew_integration/public/frontend/` |
| Asset URL prefix | `/assets/cashew_integration/frontend/` |
| Source | `frontend/src/` |

## Two-terminal dev loop

```
# terminal 1 — Frappe bench
bench start

# terminal 2 — Vite dev server (HMR)
cd apps/cashew_integration/frontend
yarn dev
# → http://0.0.0.0:8080
```

The vite dev server proxies API calls to the bench (see `proxyOptions.js`).
Visit `http://<site>:8080` for fast HMR; Frappe session cookie flows
through the proxy.

## Production build

`bench build --app cashew_integration` runs `yarn build` in `frontend/`,
which:

1. Compiles assets into `cashew_integration/public/frontend/`
2. Copies `index.html` → `cashew_integration/www/frontend.html` via the
   frappe-ui `buildConfig` plugin

`public/frontend/` is gitignored; `www/frontend.html` is committed (D4).

## State management

f010 D6: **frappe-ui `createResource` + module-scope composables**. No
`pinia`, no `*-persistedstate`, and no `localStorage` / `sessionStorage`
writes anywhere in `src/`. Session-only view state by design.

## Architecture references

- `apps/cashew_integration/.fb/features/f010-cashew-frontend-spa/arch/decisions.md`
  (D1–D14)
- `apps/cashew_integration/.fb/features/f010-cashew-frontend-spa/arch/decisions-b.md`
  (Amendment 1 — Custom accent color)
- `apps/cashew_integration/CLAUDE.md` — SPA hosting + API rules
