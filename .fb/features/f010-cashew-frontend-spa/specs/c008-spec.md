# c008 — realtime-client

> **Type:** ui-infra (single module + minor server pre-flight)
> **Depends on:** c004 (shell uses `setRealtimeStatus`; pages call
> `subscribeList` / `subscribeDoc`), c011 (server emission audit — runs
> in parallel)
> **Arch refs:** D8 (Socket.IO subscription + 30s polling fallback),
> D14 (Cashew Settings doc_update propagates theme)
> **Consumers:** c005 (list), c006 (per-run), c007 (list debounced 2s),
> c012 (Cashew Settings theme propagation)

---

## Overview

One module — `frontend/src/realtime.js` — that:

1. Opens a Frappe-realtime Socket.IO connection on first
   `subscribeList` / `subscribeDoc` call.
2. Exposes three subscribe helpers: `subscribeList(doctype, cb)`,
   `subscribeDoc(doctype, name, cb)`, `subscribeSettings(cb)`.
3. Tracks connection state and pushes it to c004's
   `setRealtimeStatus(state)` for the shell indicator.
4. On permanent socket loss (>10s), starts a 30s polling fallback for
   each `subscribeDoc('Cashew Import Run', ...)` active subscription
   via `cashew_integration.api.get_run_progress(run_name)`.
5. Hooks `Cashew Settings` doc_update → calls c004's
   `applyThemeFromDoc(doc)` so theme propagates across all open SPA
   tabs (D14).

All session-only; no persistence; no localStorage.

---

## Connection bootstrap

Use Frappe's `frappe.realtime` helper if globally exposed (it is, via
the `frappe` global injected by `www/cashew.html`); else fall back to
raw `socket.io-client`:

```js
// frontend/src/realtime.js
import { io } from 'socket.io-client'
import { setRealtimeStatus, applyThemeFromDoc } from '@/state/useRealtimeStatus'
import { useTheme } from '@/state/useTheme'

let socket = null
let activeSubs = new Map()   // key -> Set of callbacks
let activeRunPolls = new Map() // run_name -> intervalId
let permanentLossTimer = null
const PERMANENT_LOSS_MS = 10_000
const POLL_INTERVAL_MS = 30_000

function ensureSocket() {
  if (socket) return socket

  // Frappe's runtime exposes window.frappe.socketio_port when bench is
  // running. Production uses same-origin /socket.io path. Match the
  // CRM pattern: use frappe-injected window.frappe.realtime if available;
  // else open our own.
  if (typeof window !== 'undefined' && window.frappe?.realtime?.socket) {
    socket = window.frappe.realtime.socket
  } else {
    const path = '/socket.io'
    const auth = { token: window.boot?.realtime_token }
    socket = io({ path, auth, transports: ['websocket', 'polling'], reconnection: true })
  }

  socket.on('connect',    onConnect)
  socket.on('disconnect', onDisconnect)
  socket.on('connect_error', onError)
  socket.on('reconnecting',  () => setRealtimeStatus('reconnecting'))
  socket.on('reconnect',     onConnect)

  // Frappe core events
  socket.on('doc_update', onDocUpdate)
  socket.on('list_update', onListUpdate)

  return socket
}

function onConnect() {
  clearTimeout(permanentLossTimer); permanentLossTimer = null
  stopAllRunPolls()
  setRealtimeStatus('connected')
}

function onDisconnect() {
  setRealtimeStatus('reconnecting')
  permanentLossTimer = setTimeout(() => {
    setRealtimeStatus('disconnected')
    startAllRunPolls()
  }, PERMANENT_LOSS_MS)
}

function onError() { setRealtimeStatus('reconnecting') }
```

---

## Frappe realtime event shapes

Frappe emits:

- `doc_update` with payload `{ doctype, name, modified, ...changedFields }`
  (Frappe core sends the full doctype + name plus a subset of changed
  fields. The exact field set depends on `frappe.db.set_value` vs
  `doc.save`; for `set_value(..., notify=True)` it's the changed
  field + value; for `doc.save` it's a much larger doc summary.)

- `list_update` is the SPA-side helper event some frappe-ui consumers
  use; if not natively emitted by Frappe v15/16, we synthesize it from
  `doc_update` events by filtering on `doctype`.

`onDocUpdate` normalizes:

```js
function onDocUpdate(payload) {
  const { doctype, name } = payload || {}
  if (!doctype || !name) return

  // 1. List subscribers (every doc change in a doctype refreshes its list)
  const listKey = listKeyFor(doctype)
  if (activeSubs.has(listKey)) {
    for (const cb of activeSubs.get(listKey)) cb(payload)
  }

  // 2. Doc subscribers
  const docKey = docKeyFor(doctype, name)
  if (activeSubs.has(docKey)) {
    // Build a normalized event shape consumers can rely on
    const event = normalizeDocEvent(payload)
    for (const cb of activeSubs.get(docKey)) cb(event)
  }

  // 3. Cashew Settings theme propagation (D14)
  if (doctype === 'Cashew Settings') {
    onCashewSettingsUpdate(payload)
  }
}

function normalizeDocEvent(payload) {
  // c006 expects { doc?: partialDoc, rows?: [{ row_idx, ...partial }] }
  // Frappe's raw payload may not carry rows; for a Cashew Import Run
  // doc_update we deliver { doc: payload } and let consumers re-fetch
  // rows via get_doc when status changes. For raw set_value writes
  // that touch import_rows, the server hook (c011) publishes a
  // synthetic event with shape { doc: {name, ...}, rows: [{...}] }.
  if (payload.rows) return { doc: payload, rows: payload.rows }
  return { doc: payload }
}
```

`listKeyFor(doctype) = 'list:' + doctype`.
`docKeyFor(doctype, name) = 'doc:' + doctype + ':' + name`.

---

## `Cashew Settings` theme propagation (D14)

```js
function onCashewSettingsUpdate(payload) {
  // payload should carry accent_color + accent_color_custom; if it
  // doesn't, fetch the singleton.
  if (payload.accent_color != null) {
    applyThemeFromDoc({
      accent_color: payload.accent_color,
      accent_color_custom: payload.accent_color_custom,
    })
    return
  }
  // fallback fetch
  fetch('/api/method/frappe.client.get_value', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': window.boot.csrf_token,
    },
    body: JSON.stringify({
      doctype: 'Cashew Settings',
      filters: 'Cashew Settings',
      fieldname: ['accent_color', 'accent_color_custom'],
    }),
  })
    .then(r => r.json())
    .then(j => applyThemeFromDoc(j.message))
    .catch(() => {})
}
```

`applyThemeFromDoc` is the c004 ThemeController function — it accepts
`{ accent_color, accent_color_custom }`, resolves to the CSS-var quad,
and writes them on `<html>`. Effect is visual-only; no page reload.

For c012 settings page, after a successful save of `accent_color`, the
server will emit `doc_update` for Cashew Settings; this handler picks
it up everywhere (including the saving tab, which is fine — re-applies
the same values).

---

## Public API: `subscribeList` / `subscribeDoc` / `subscribeSettings`

```js
/**
 * Subscribe to list-level changes for a doctype.
 * Callback fires on any doc_update for that doctype.
 * Returns an unsubscribe function.
 */
export function subscribeList(doctype, cb) {
  ensureSocket()
  const key = listKeyFor(doctype)
  if (!activeSubs.has(key)) activeSubs.set(key, new Set())
  activeSubs.get(key).add(cb)
  // Tell server we care (Frappe's standard helper if available)
  socket?.emit?.('doctype_subscribe', { doctype })
  return () => {
    activeSubs.get(key)?.delete(cb)
    if (activeSubs.get(key)?.size === 0) {
      socket?.emit?.('doctype_unsubscribe', { doctype })
    }
  }
}

/**
 * Subscribe to a single doc's updates. Returns unsubscribe.
 */
export function subscribeDoc(doctype, name, cb) {
  ensureSocket()
  const key = docKeyFor(doctype, name)
  if (!activeSubs.has(key)) activeSubs.set(key, new Set())
  activeSubs.get(key).add(cb)
  socket?.emit?.('doc_subscribe', { doctype, name })

  // Track for run-poll fallback
  if (doctype === 'Cashew Import Run') {
    activeRunPolls.set(name, null)  // null = no poll running yet
  }

  return () => {
    activeSubs.get(key)?.delete(cb)
    if (activeSubs.get(key)?.size === 0) {
      socket?.emit?.('doc_unsubscribe', { doctype, name })
      stopRunPoll(name)
      activeRunPolls.delete(name)
    }
  }
}

/**
 * Subscribe to Cashew Settings (singleton). Wired automatically by
 * the module; pages don't usually call this. Available for tests.
 */
export function subscribeSettings(cb) {
  return subscribeDoc('Cashew Settings', 'Cashew Settings', cb)
}
```

---

## Polling fallback

```js
function startAllRunPolls() {
  for (const name of activeRunPolls.keys()) startRunPoll(name)
}
function stopAllRunPolls() {
  for (const name of [...activeRunPolls.keys()]) stopRunPoll(name)
}

function startRunPoll(name) {
  if (activeRunPolls.get(name)) return  // already polling
  const intervalId = setInterval(() => pollRun(name), POLL_INTERVAL_MS)
  activeRunPolls.set(name, intervalId)
  pollRun(name)   // first tick immediately
}

function stopRunPoll(name) {
  const intervalId = activeRunPolls.get(name)
  if (intervalId) {
    clearInterval(intervalId)
    activeRunPolls.set(name, null)
  }
}

async function pollRun(name) {
  try {
    const res = await fetch(
      `/api/method/cashew_integration.api.get_run_progress?run_name=${encodeURIComponent(name)}`,
      { headers: { 'X-Frappe-CSRF-Token': window.boot.csrf_token } },
    )
    if (!res.ok) return
    const json = await res.json()
    const progress = json.message
    // Synthesize a doc_update event
    const key = docKeyFor('Cashew Import Run', name)
    const event = normalizeDocEvent({
      doctype: 'Cashew Import Run',
      name,
      ...progress,
    })
    activeSubs.get(key)?.forEach(cb => cb(event))
  } catch (e) {
    // ignore; next tick retries
  }
}
```

`cashew_integration.api.get_run_progress(run_name)` already exists in
the codebase (see api.py); response shape (verify at impl):
`{ status, rows_total, rows_valid, rows_failed, rows_posted,
rows_skipped, started_on, finished_on }`. If the SPA needs per-row
patches under polling, extend get_run_progress to return changed-since
rows — out of scope for c008 v1 (counters are enough; per-row state
catches up on next manual refresh / when socket reconnects).

---

## Reconnect → realtime status state machine

Drives the c004 RealtimeStatusIndicator (4-state palette).

| Trigger | New state |
|---|---|
| `socket.on('connect')` | `connected` |
| `socket.on('disconnect')` (transient) | `reconnecting` |
| Disconnect persists >10s | `disconnected` + start polling |
| `socket.on('reconnect')` | `connected` + stop polling |
| Module never initialized | `unknown` (c004 default) |

c004's `setRealtimeStatus(state)` writes to the
`useRealtimeStatus()` ref; the indicator re-renders automatically.

---

## Hook into c004's stubs

c004 exported two named functions/refs from `src/state/useRealtimeStatus.js`:

```js
// already exists from c004 (stubbed):
export const realtimeStatus = ref('unknown')
export function setRealtimeStatus(s) { realtimeStatus.value = s }
export function useRealtimeStatus() { return realtimeStatus }
```

c004 also exported `applyThemeFromDoc` from `src/theme.js`. c008 imports
both:

```js
import { setRealtimeStatus } from '@/state/useRealtimeStatus'
import { applyThemeFromDoc } from '@/theme'
```

---

## Module initialization

`src/realtime.js` is imported by any page that calls a subscribe
helper. `ensureSocket()` is idempotent. To wire the `Cashew Settings`
theme subscription regardless of which page is open, `src/main.js`
(extended from c004) calls:

```js
// in src/main.js (extend c004's main.js)
import { subscribeSettings } from '@/realtime'

app.mount('#app')

subscribeSettings(() => { /* handled inside the module; cb is a no-op */ })
```

The subscription stays open for the lifetime of the SPA. Unsubscribing
on `beforeunload` is unnecessary — the connection closes when the tab
does.

---

## Files touched

```
frontend/src/realtime.js                            # NEW — this spec's module
frontend/src/main.js                                # EDIT — add subscribeSettings() init line
frontend/src/state/useRealtimeStatus.js             # NO CHANGE (stubbed in c004)
frontend/src/theme.js                               # NO CHANGE (applyThemeFromDoc exported by c004)
```

No new Python. `c011` audits the server-side worker code paths for
emission discipline (see that spec).

Boot dict already carries `realtime_token` (c002 spec). No new boot
field needed.

---

## Acceptance

- [ ] First call to `subscribeList` / `subscribeDoc` opens a single
      socket (idempotent — subsequent calls reuse it).
- [ ] On `connect`, `useRealtimeStatus()` flips to `'connected'`.
- [ ] On `disconnect`, flips to `'reconnecting'`; after 10s sustained,
      flips to `'disconnected'`.
- [ ] On `reconnect`, flips back to `'connected'`.
- [ ] `subscribeList('Cashew Import Run', cb)` → cb fires when any
      Cashew Import Run is saved or set_value'd on the server.
- [ ] `subscribeDoc('Cashew Import Run', 'XYZ', cb)` → cb fires only
      for that doc.
- [ ] Returned unsubscribe fn detaches the callback; if it was the last
      callback for that key, the module emits `doc_unsubscribe` /
      `doctype_unsubscribe`.
- [ ] During `disconnected`, every subscribed `Cashew Import Run` doc
      receives `get_run_progress` polls every 30s; first poll fires
      immediately on entering disconnected state.
- [ ] On reconnect, all polls stop.
- [ ] `Cashew Settings` doc_update propagates theme — change accent_color
      on the server (e.g. via Desk form) and within ~1s every open SPA
      tab re-applies the CSS vars. No page reload required.
- [ ] If `Cashew Settings` doc_update payload doesn't carry
      `accent_color`, fallback fetch via `frappe.client.get_value`
      retrieves it and applies.
- [ ] No `localStorage` / `sessionStorage` writes in `realtime.js`
      (grep zero).
- [ ] Module-level `socket`, `activeSubs`, `activeRunPolls` are not
      exported (encapsulated).

---

## Pre-flight: c011 audit (separate spec)

For c008 to deliver, every server code path that mutates a
`Cashew Import Run` must emit a `doc_update` event:

- `frappe.db.set_value('Cashew Import Run', name, ...)` — auto-emits
  (when `notify=True`; verify Frappe v15/16 default).
- `doc.save()` on a Cashew Import Run document — auto-emits.
- Bare SQL `UPDATE \`tabCashew Import Run\` SET ...` — does NOT emit;
  needs a paired `frappe.publish_realtime('doc_update', ...)`.

c011 walks the worker code under `cashew_integration/` and adds
emissions where missing. c008 ships first; c011 follows during the
same iteration.

---

## TD calls inside arch envelope (not surfacing)

- **Idempotent `ensureSocket()`.** Module-singleton socket; pages
  don't open their own connection.
- **`Set`-backed callback registries.** Multiple components on the
  same doc/key OK; each unsubscribe pulls itself out.
- **Polling fires immediately on entering disconnected** (no 30s wait
  for first poll). Operator gets fresh data fast.
- **Cashew Settings theme propagation handled inside the module**,
  not in c012. Reason: it should run regardless of which page the user
  is on — Settings page, Dashboard, Run Workspace, etc. Centralizing
  here means c012 only needs to save; propagation is free.
- **Reusing `window.frappe.realtime.socket` when available.** Frappe
  v15/16's `realtime.js` runtime already opens a socket the moment the
  user logs in (for desk-page events). If our boot script can hook
  that, we share one connection. If not, we open our own.

---

## Open items (handed off)

- **`window.frappe.realtime.socket` availability under www/ route.**
  Verify on first dev. CRM's www/crm.py loads frappe runtime via
  `frappe.app.include_js`; doppio's c001/c002 may or may not match.
  If absent, our own `io()` open is the fallback; either way the
  module is correct.
- **`socket.emit('doctype_subscribe', ...)` exact event name.** Frappe
  v15/16 may use a different event name; verify and update. Worst
  case: skip the emit (subscribed-everything is the Frappe default
  for the room-by-doctype model in some versions).
- **`payload` shape of `doc_update`.** Verify whether it carries
  enough fields to drive the SPA without a follow-up `get_doc`. If
  not, consumers handle that themselves (c006 already does via
  `useRun.reload()` on status change).
- **`Cashew Settings` payload field set.** If it doesn't include
  `accent_color`, the fallback fetch covers it. Optimization: extend
  the server emission (c011) to include the relevant fields.
- **Reconnect storm.** If many tabs reconnect simultaneously after a
  server restart, polling-then-reconnect could cause a small spike.
  Negligible at Cashew's scale; revisit if it shows in metrics.
