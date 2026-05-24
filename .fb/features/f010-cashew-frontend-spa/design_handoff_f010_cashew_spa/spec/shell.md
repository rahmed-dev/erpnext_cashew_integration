# App Shell — Cashew SPA

**Component:** `c004 spa-router-shell`
**Purpose:** Persistent chrome around every page in the Cashew SPA. Provides navigation, app identity, and shell-level concerns (error toasts, realtime indicator). Same shell wraps Finance Dashboard, Imports List, and Run Workspace.

This document is for the design tool. Every page brief references this shell — Designer should render the shell identically on all three pages.

---

## Audience

Finance operators and managers who already use ERPNext for accounting. Logged in via same-origin Frappe session. Roles: `System Manager` or `Accounts Manager`.

## Mounted at

`/cashew` (catch-all, served by `cashew_integration/www/cashew.html`). Vue Router (HTML5 history) takes over client-side.

---

## Visual Tone

- Frappe-ui look-and-feel (Tailwind utility classes + frappe-ui primitives). Light theme.
- Functional, dense, finance-app feel. Not playful.
- Sidebar is darker / muted than content area for visual separation.
- Body uses generous whitespace + clear hierarchy; not a marketing site, not a Desk form.

---

## Layout

Fixed two-column on desktop / tablet. Collapsible single-column on mobile.

```
┌─────────────────┬──────────────────────────────────────────┐
│                 │                                          │
│  [App Switcher] │                                          │
│                 │           PAGE CONTENT                   │
│  ─────────────  │           (varies per route)             │
│                 │                                          │
│  📊  Dashboard  │                                          │
│  📄  Imports    │                                          │
│                 │                                          │
│                 │                                          │
│  ─────────────  │                                          │
│                 │                                          │
│  [User chip ⌄]  │                                          │
│  [● connected]  │                                          │
│                 │                                          │
└─────────────────┴──────────────────────────────────────────┘
   sidebar              content area
   ~240px wide          fluid
```

### Sidebar regions (top-to-bottom)

1. **App Switcher** — dropdown at the very top.
2. **Primary Nav** — vertical list of page links.
3. *(flexible space)*
4. **User Chip + Realtime Status** — at the bottom.

### Content area

Pure page content. Pages own their own header (page title, action bar, period selector, etc.). Shell does NOT inject a global page header.

---

## Components

### 1. AppSwitcher (top of sidebar)

**Purpose:** Identify the current app and let the user exit back to the Desk (or, in future, jump to another app).

**Display:**
- Cashew logo (24×24 SVG, served from `/assets/cashew_integration/images/cashew-app-icon.svg`)
- App label text: `Cashew`
- Chevron-down (lucide `chevron-down`) to indicate the dropdown

**Dropdown menu items (click switcher to open):**

| Label | Icon | Target | Notes |
|---|---|---|---|
| Cashew (current) | cashew logo | (no-op / `/`) | Marked active; clicking closes dropdown |
| Back to Desk | `arrow-left` | `/app` | Hard navigation; leaves SPA |
| *Future apps will append here* | | | Not in v1 — section can be omitted |

**Behaviour:**
- Click switcher chip → open menu
- Click outside or pick item → close menu
- Keyboard: `Esc` closes; `↑↓` navigates items; `Enter` selects

**States:**
- Default
- Open (dropdown visible)
- (no loading/empty/error — static content)

---

### 2. PrimaryNav

**Purpose:** Main page navigation. Two items in v1.

**Items:**

| # | Icon (lucide) | Label | Route | Active when |
|---|---|---|---|---|
| 1 | `bar-chart-2` | Dashboard | `/` | Path is exactly `/` |
| 2 | `file-text` | Imports | `/runs` | Path starts with `/runs` (covers list + workspace) |

**Display per item:** Icon (20×20) + label, left-aligned, full sidebar width clickable. Active item is visually distinct (filled background + bold text or accent border).

**States:**
- Default
- Hover (subtle background tint)
- Active (filled background + accent stripe on the left edge)
- Focus-visible (keyboard focus ring)

**Mobile behaviour:** Sidebar collapses to a hamburger button in a top-bar; tapping opens an overlay drawer with the same items.

---

### 3. UserChip (bottom of sidebar)

**Purpose:** Show the current user; minor sign-out / profile UX.

**Display:**
- Avatar circle (Frappe user image if set, else initials)
- User full name (truncate if long)
- Chevron-down — opens a small menu

**Menu items:**
| Label | Target |
|---|---|
| Settings | `/app/cashew-settings` (back to Desk single doc) |
| Help | `https://docs.frappe.io` *(or wherever)* — placeholder, can omit v1 |
| Sign out | `/api/method/logout` (Frappe standard) |

**Data source:** `window.boot.session_user` (full name + image fetched once on mount via `frappe.client.get_value('User', user, ['full_name', 'user_image'])`).

**States:** Default, menu-open.

---

### 4. RealtimeStatusIndicator

**Purpose:** Tell the user whether the SPA is receiving live updates (per D8).

**Display:** Small dot + tiny label, beside or below the UserChip.

| State | Dot color | Label | Source |
|---|---|---|---|
| Connected | green | `Live` | Socket.IO connected |
| Reconnecting | amber, pulsing | `Reconnecting…` | Transient drop, retrying |
| Polling fallback | grey | `Polling` | Permanent socket failure; using 30s poll (D8 fallback) |
| Disconnected | red | `Offline` | Network down |

Hover/tap shows a small tooltip with the underlying detail (e.g. "Last update 12s ago").

**Behaviour:** Compact by default. Not attention-grabbing unless the state is bad.

---

### 5. ErrorToastBoundary (shell-level, invisible)

**Purpose:** Catch every 403 / "Permission denied" / network error from any `/api/*` call and surface a non-intrusive toast at the bottom-right. Per D5.c.

**Display:** Stacked toasts, dismissible, auto-dismiss after 5s.

**Toast content:**
- Icon (alert-circle for errors, info for info)
- Title (short, e.g. "Permission denied")
- Body (the API error message, truncated to 2 lines)
- Optional retry button (when relevant)

**Not visible by default — only renders when an event fires.**

---

## Responsive behaviour

| Breakpoint | Behaviour |
|---|---|
| Desktop (≥1024px) | Sidebar 240px fixed, content fluid |
| Tablet (640–1023px) | Sidebar 200px, content fluid |
| Mobile (<640px) | Sidebar hidden by default; hamburger button top-left of content opens an overlay drawer |

Sidebar drawer animation: slide-in from left, 200ms.

---

## Accessibility

- Sidebar nav is a `<nav>` landmark
- All nav items are anchor tags with `aria-current="page"` when active
- App switcher and user chip dropdowns use `aria-expanded` + roving tabindex
- Toast region has `aria-live="polite"`
- Color is never the only signal — every status state has an icon + label

---

## Things the shell does NOT do (so pages know to handle themselves)

- Render the page title or breadcrumb — pages own their header
- Inject a global search bar — Imports List page has its own search; dashboard doesn't need one
- Provide a notifications inbox — out of scope for v1
- Provide role-aware nav hiding — D5.c flag (closed); all logged-in users see both nav items
