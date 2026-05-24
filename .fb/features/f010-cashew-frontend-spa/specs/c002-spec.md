# c002 — spa-host-route

> **Type:** route-and-jinja-entry
> **Depends on:** (none — parallels c001)
> **Arch refs:** D2 (`www/` web page + HTML5 history catch-all), D3 (session +
> CSRF auth + role gate), D5 (boot data discipline), D8 (realtime token
> seeded at boot), D14 (accent color in boot), c013 + Amendment 1
> (accent_color + accent_color_custom fields)
> **Note on D3 refinement:** 403 behavior split by user state (Guest vs.
> logged-in-no-role). This is an implementation refinement of D3, not an
> amendment — no scope change.

---

## Overview

Three files + one icon asset land the SPA at `/cashew/*`:

1. `cashew_integration/www/cashew.py` — perm gate + boot dict builder.
2. `cashew_integration/www/cashew.html` — built shell from vite (mostly
   Doppio territory; this spec captures only TD's hard requirements).
3. `cashew_integration/hooks.py` — `website_route_rules` catch-all entry +
   Apps-screen tile metadata.
4. `cashew_integration/public/images/cashew-app-icon.svg` — Apps tile icon
   (lucide-derived, committed; designer-swap-friendly).

Decisions resolved by this spec:
- **S1.** Boot dict emits server-side default period (current month start →
  today).
- **S2.** Boot dict emits a single perm flag `can_write_settings`. All other
  perms checked per-action server-side (D5 rule 3).
- **S3.** Apps-screen icon = lucide `landmark` glyph in `--cs-accent`,
  committed as a static SVG; designer may swap later.
- **S4.** Guest → `/login?redirect-to=/cashew`; logged-in user without role
  → Frappe's stock 403 page (`PermissionError` with friendly message).

---

## `cashew_integration/www/cashew.py`

```python
import frappe
from frappe import _
from frappe.utils import getdate, get_first_day

no_cache = 1


def get_context(context):
    """Web page entry for the Cashew SPA. Runs on every /cashew/* request."""
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/cashew"
        raise frappe.Redirect

    if not check_app_permission():
        raise frappe.PermissionError(_("You don't have access to Cashew."))

    context.boot = _build_boot()
    context.no_cache = 1
    return context


def check_app_permission():
    """True if session user holds the role gate (D3.a)."""
    roles = frappe.get_roles(frappe.session.user)
    return "System Manager" in roles or "Accounts Manager" in roles


def _build_boot():
    user = frappe.session.user
    user_doc = frappe.get_cached_doc("User", user)
    settings = frappe.get_cached_doc("Cashew Settings", "Cashew Settings")
    today = getdate()
    period_start = get_first_day(today)

    return {
        # Session + auth
        "csrf_token": frappe.sessions.get_csrf_token(),
        "session_user": user,
        "session_user_full_name": user_doc.full_name or user,
        "session_user_image": user_doc.user_image,

        # Frappe defaults (driven by User Permission + global)
        "sysdefaults": {
            "default_company": frappe.defaults.get_user_default("Company"),
            "default_currency":
                frappe.defaults.get_user_default("Currency") or "PKR",
        },

        # Cashew-app config (read once at boot; live-updated via realtime D8)
        "cashew_settings": {
            "default_company": settings.company,
            "accent_color": settings.accent_color or "Indigo",
            "accent_color_custom": settings.accent_color_custom or None,
        },

        # Default period for dashboard first paint (server tz)
        "default_period_start": str(period_start),
        "default_period_end": str(today),

        # Single perm flag — others enforced server-side per call (D5.3)
        "can_write_settings": bool(
            frappe.has_permission("Cashew Settings", "write", user=user)
        ),

        # Realtime auth — c008 uses this to bootstrap Socket.IO (D8)
        # Field name pinned at Dev time per installed Frappe API.
        "realtime_token": _safe_realtime_token(),

        # Debug + telemetry hooks (future Sentry tagging)
        "app_version": _safe_app_version(),
    }


def _safe_realtime_token():
    try:
        return frappe.realtime.get_user_info().get("sid")
    except Exception:
        return None


def _safe_app_version():
    try:
        return frappe.get_attr("cashew_integration.__version__")
    except Exception:
        return None
```

**Dev notes:**
- `frappe.sessions.get_csrf_token()` is the Frappe v15/v16 accessor for the
  current session's CSRF token. Verify against the installed bench version
  (`bench --site work.local console` → `frappe.sessions.get_csrf_token()`).
- `frappe.realtime.get_user_info()` returns the socket auth info; the
  `sid` key is what `socket.io-client` needs. If Frappe v16 renames the
  API, adjust `_safe_realtime_token()` — c008 spec consumes whatever this
  emits.
- `get_cached_doc("User", user)` is the standard pattern (CRM uses it).
- `get_first_day(today)` returns first calendar day of `today.month`.
- `frappe.Redirect` is the right exception for guest redirect (Frappe's
  redirect mechanism reads `frappe.local.flags.redirect_location`).
- `frappe.PermissionError` with a translated message renders Frappe's
  stock no-access page. Do not use `frappe.throw` here — `raise` is more
  explicit and surfaces in `boot.py` trace.

---

## `cashew_integration/www/cashew.html`

Vite build output. Doppio's build hook (c003) copies `frontend/dist/index.html`
to this path on every `bench build --app cashew_integration`. **Committed
to git** (per D4).

Hard requirements (vite + Doppio template usually satisfies these out of the
box; verify after first build):

1. **Boot dict serialization.** Before the bundle `<script>` tag, the file
   must emit:
   ```html
   <script>
     window.boot = {{ boot | tojson }};
   </script>
   ```
   This Jinja expression is rendered by `cashew.py`'s `get_context`. If
   Doppio's template uses a different variable name (`bootInfo`,
   `pageBoot`), keep that and inject the same shape — the SPA reads
   whatever key Doppio chose.

2. **Mount point.** `<div id="app"></div>` (or whatever Doppio's vite
   template emits — Vue mounts to that selector via `main.js`).

3. **Hashed asset URLs.** All `<script src=...>` and `<link href=...>`
   tags use vite's content-hashed names (`index-<hash>.js`,
   `index-<hash>.css`). Doppio/vite does this automatically; manual edits
   forbidden — they'll be overwritten on next build.

4. **No inline app logic.** No JS beyond `window.boot = ...` and the
   bundle `<script>` tag.

5. **Cache headers respect `no_cache=1`** — `cashew.py` sets this; Frappe
   adds `Cache-Control: no-store` automatically.

**Idiomatic content (Doppio template output, after `yarn build` runs):**
```html
{# Auto-generated by vite; do not edit by hand. Re-emitted on bench build. #}
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Cashew</title>
  <link rel="icon" type="image/svg+xml"
        href="/assets/cashew_integration/images/cashew-app-icon.svg" />
  <link rel="stylesheet"
        href="/assets/cashew_integration/frontend/assets/index-<hash>.css" />
</head>
<body>
  <div id="app"></div>
  <script>
    window.boot = {{ boot | tojson }};
  </script>
  <script type="module"
          src="/assets/cashew_integration/frontend/assets/index-<hash>.js">
  </script>
</body>
</html>
```

The exact tag order + element names follow Doppio's vite template. Spec
captures the contract, not the literal output.

---

## `cashew_integration/hooks.py` additions

Append (or create) these top-level assignments:

```python
# --- Cashew SPA (f010) --------------------------------------------------

website_route_rules = [
    # Catch-all: /cashew/<anything> -> www/cashew.* (HTML5 history routing)
    {"from_route": "/cashew/<path:app_path>", "to_route": "cashew"},
]

app_icon_url = "/assets/cashew_integration/images/cashew-app-icon.svg"
app_icon_route = "/cashew"
app_icon_title = "Cashew"
```

**Dev notes:**
- `website_route_rules` is additive — if `hooks.py` already has the
  variable, merge the new dict into the existing list.
- The catch-all rule does NOT cover `/cashew` itself (no trailing
  segment). Frappe's normal `www/cashew.html` resolution handles the
  exact match. Together they cover every SPA route.
- Apps screen tile (`app_icon_*` trio) is what makes "Cashew" appear in
  `/app` for users with the role gate. Frappe reads these at app
  install + on `bench migrate`.

---

## `cashew_integration/public/images/cashew-app-icon.svg`

24×24 viewBox lucide `landmark` glyph, recolored to `currentColor` so it
inherits whatever color the parent renders. Frappe's Apps tile renders it
at ~32px with the user's theme background.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 22h18" />
  <path d="M6 18v-7" />
  <path d="M10 18v-7" />
  <path d="M14 18v-7" />
  <path d="M18 18v-7" />
  <path d="M2 11h20" />
  <path d="M12 2 2 8h20Z" />
</svg>
```

**Why this glyph:** financial / treasury connotation. Reads cleanly at 16/24/32px. Lucide-licensed for redistribution.

**Designer override path:** swap this file; commit the new SVG. No code change required. Filename is the only contract.

---

## Data flow

```mermaid
sequenceDiagram
  participant Browser
  participant Frappe as Frappe (cashew.py)
  participant DB
  Browser->>Frappe: GET /cashew (or /cashew/runs/abc)
  Frappe->>Frappe: get_context()
  alt user == Guest
    Frappe-->>Browser: 302 /login?redirect-to=/cashew
  else user has role
    Frappe->>DB: get_cached_doc User, Cashew Settings
    Frappe->>Frappe: build boot dict
    Frappe-->>Browser: 200 cashew.html (boot embedded, no-cache)
    Browser->>Browser: window.boot = {...}; Vue mounts; router takes over
  else user lacks role
    Frappe-->>Browser: 403 no-access page
  end
```

---

## Permissions summary

| Surface | Who | Gate | Where enforced |
|---|---|---|---|
| `/cashew` route | Guest | redirect to `/login` | `cashew.py: get_context` |
| `/cashew` route | Logged-in, no role | 403 page | `cashew.py: check_app_permission` |
| `/cashew` route | System Manager OR Accounts Manager | allowed | `cashew.py: check_app_permission` |
| Cashew Settings write button (c012) | logged-in user with role | hidden / read-only mode if `!can_write_settings` | `boot.can_write_settings` |
| All other writes | role + per-doctype perm | server enforces per call | D5 rule 3 |

---

## Files touched by Dev

```
cashew_integration/www/cashew.py                                (NEW)
cashew_integration/www/cashew.html                              (NEW — vite output, committed)
cashew_integration/hooks.py                                     (EDIT — add 4 module-level assignments)
cashew_integration/public/images/cashew-app-icon.svg            (NEW)
```

No new fixtures, no DocType changes, no new whitelisted methods.

---

## Acceptance

- [ ] As `Administrator` (System Manager): `/cashew` returns 200, renders
      shell, `window.boot.session_user == "Administrator"`,
      `window.boot.can_write_settings == true`.
- [ ] As a user with only `Accounts Manager`: same — 200, renders, boot
      populated.
- [ ] As a user with only `System User`: `/cashew` returns 403 (Frappe's
      no-access page with the "You don't have access to Cashew" message).
- [ ] As Guest: `/cashew` returns 302 redirect to
      `/login?redirect-to=/cashew`.
- [ ] `/cashew/runs`, `/cashew/runs/RUN-001`, `/cashew/settings` all serve
      the same shell (verify in browser DevTools: same HTML response body).
- [ ] `window.boot.csrf_token` is non-empty and matches
      `frappe.sessions.get_csrf_token()` in `bench --site work.local console`.
- [ ] `window.boot.accent_color` matches the current Cashew Settings value
      (test with both a preset + Custom).
- [ ] `window.boot.cashew_settings.accent_color_custom` is `null` when
      Cashew Settings has a preset selected.
- [ ] `window.boot.default_period_start` == first day of current month,
      `default_period_end` == today (in site timezone).
- [ ] Apps screen at `/app` shows a "Cashew" tile with the landmark icon
      for users with the role gate; tile click navigates to `/cashew`.
- [ ] Response headers include `Cache-Control: no-store` (no-cache=1
      working).
- [ ] After changing Cashew Settings via Desk, the next `/cashew` page
      load reflects the new accent_color in `window.boot` (proves no
      stale cache).

---

## Open items (handed off)

- `realtime_token` exact API name — c008 verifies at integration time
  against installed Frappe v16. If `frappe.realtime.get_user_info()`
  doesn't ship the right info, c008 falls back to fetching `sid` after
  SPA boot.
- ThemeController logic (apply `boot.accent_color` + derive shades) →
  c004.
- Boot dict consumption (`window.boot` → composable adapter) → c004
  (in `src/boot.js` per c001 layout).
- `app_icon_url` Frappe migration: after first install, may need
  `bench --site work.local migrate` to register the tile. Documented
  in c003 dev loop.
- Designer-authored SVG swap: out of scope; comment block in the SVG
  notes "swap with brand asset; filename + viewBox must match".
