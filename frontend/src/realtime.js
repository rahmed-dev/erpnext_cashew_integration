// f010 c008 — realtime client (D8 + D14).
// Opens a Frappe Socket.IO connection on first subscribe call. Exposes
// subscribeList / subscribeDoc / subscribeSettings. Drives the shell's
// realtime status indicator (c004 state). On permanent socket loss (>10s),
// starts a 30s polling fallback for each active Cashew Import Run sub.

import { io } from 'socket.io-client';
import { setRealtimeStatus } from '@/state/useRealtimeStatus';
import { applyThemeFromDoc } from '@/theme';

const PERMANENT_LOSS_MS = 10_000;
const POLL_INTERVAL_MS = 30_000;

let socket = null;
const activeSubs = new Map();        // key -> Set<cb>
const activeRunPolls = new Map();    // run_name -> intervalId | null
let permanentLossTimer = null;

const listKeyFor = (doctype) => `list::${doctype}`;
const docKeyFor = (doctype, name) => `doc::${doctype}::${name}`;

function ensureSocket() {
  if (socket) return socket;

  if (typeof window !== 'undefined' && window.frappe?.realtime?.socket) {
    socket = window.frappe.realtime.socket;
  } else if (typeof window !== 'undefined') {
    const port = window.boot?.socketio_port || 9000;
    const url = `${window.location.protocol}//${window.location.hostname}:${port}`;
    const auth = { token: window.boot?.realtime_token };
    socket = io(url, {
      auth,
      withCredentials: true,
      transports: ['websocket', 'polling'],
      reconnection: true,
    });
  } else {
    return null;
  }

  socket.on('connect', onConnect);
  socket.on('disconnect', onDisconnect);
  socket.on('connect_error', onError);
  socket.on('reconnecting', () => setRealtimeStatus('reconnecting'));
  socket.on('reconnect', onConnect);

  socket.on('doc_update', onDocUpdate);
  socket.on('list_update', onListUpdate);

  return socket;
}

function onConnect() {
  if (permanentLossTimer) {
    clearTimeout(permanentLossTimer);
    permanentLossTimer = null;
  }
  stopAllRunPolls();
  setRealtimeStatus('connected');
}

function onDisconnect() {
  setRealtimeStatus('reconnecting');
  if (permanentLossTimer) clearTimeout(permanentLossTimer);
  permanentLossTimer = setTimeout(() => {
    setRealtimeStatus('disconnected');
    startAllRunPolls();
  }, PERMANENT_LOSS_MS);
}

function onError() {
  setRealtimeStatus('reconnecting');
}

function onDocUpdate(payload) {
  const { doctype, name } = payload || {};
  if (!doctype || !name) return;

  const listKey = listKeyFor(doctype);
  if (activeSubs.has(listKey)) {
    for (const cb of activeSubs.get(listKey)) cb(payload);
  }
  const docKey = docKeyFor(doctype, name);
  if (activeSubs.has(docKey)) {
    for (const cb of activeSubs.get(docKey)) cb(payload);
  }

  if (doctype === 'Cashew Settings') onCashewSettingsUpdate(payload);
}

function onListUpdate(payload) {
  const { doctype } = payload || {};
  if (!doctype) return;
  const listKey = listKeyFor(doctype);
  if (activeSubs.has(listKey)) {
    for (const cb of activeSubs.get(listKey)) cb(payload);
  }
}

export function subscribeList(doctype, cb) {
  ensureSocket();
  const key = listKeyFor(doctype);
  if (!activeSubs.has(key)) activeSubs.set(key, new Set());
  activeSubs.get(key).add(cb);
  socket?.emit?.('doctype_subscribe', { doctype });
  return () => {
    activeSubs.get(key)?.delete(cb);
    if (activeSubs.get(key)?.size === 0) {
      socket?.emit?.('doctype_unsubscribe', { doctype });
      activeSubs.delete(key);
    }
  };
}

export function subscribeDoc(doctype, name, cb) {
  ensureSocket();
  const key = docKeyFor(doctype, name);
  if (!activeSubs.has(key)) activeSubs.set(key, new Set());
  activeSubs.get(key).add(cb);
  socket?.emit?.('doc_subscribe', { doctype, name });

  if (doctype === 'Cashew Import Run' && !activeRunPolls.has(name)) {
    activeRunPolls.set(name, null);
  }

  return () => {
    activeSubs.get(key)?.delete(cb);
    if (activeSubs.get(key)?.size === 0) {
      socket?.emit?.('doc_unsubscribe', { doctype, name });
      activeSubs.delete(key);
      if (doctype === 'Cashew Import Run') {
        stopRunPoll(name);
        activeRunPolls.delete(name);
      }
    }
  };
}

export function subscribeSettings(cb) {
  ensureSocket();
  const key = docKeyFor('Cashew Settings', 'Cashew Settings');
  if (!activeSubs.has(key)) activeSubs.set(key, new Set());
  if (typeof cb === 'function') activeSubs.get(key).add(cb);
  socket?.emit?.('doc_subscribe', { doctype: 'Cashew Settings', name: 'Cashew Settings' });
  return () => {
    if (typeof cb === 'function') activeSubs.get(key)?.delete(cb);
  };
}

function onCashewSettingsUpdate(payload) {
  if (payload && (payload.accent_color != null || payload.accent_color_custom != null)) {
    applyThemeFromDoc({
      accent_color: payload.accent_color,
      accent_color_custom: payload.accent_color_custom,
    });
    return;
  }
  if (typeof window === 'undefined') return;
  fetch('/api/method/frappe.client.get_value', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': window.boot?.csrf_token || window.csrf_token || '',
    },
    body: JSON.stringify({
      doctype: 'Cashew Settings',
      filters: 'Cashew Settings',
      fieldname: ['accent_color', 'accent_color_custom'],
    }),
  })
    .then((r) => r.json())
    .then((j) => applyThemeFromDoc(j?.message || {}))
    .catch(() => {});
}

// Polling fallback ---------------------------------------------------------

function startAllRunPolls() {
  for (const name of activeRunPolls.keys()) startRunPoll(name);
}

function stopAllRunPolls() {
  for (const name of [...activeRunPolls.keys()]) stopRunPoll(name);
}

function startRunPoll(name) {
  if (activeRunPolls.get(name)) return;
  const intervalId = setInterval(() => pollRun(name), POLL_INTERVAL_MS);
  activeRunPolls.set(name, intervalId);
  pollRun(name);
}

function stopRunPoll(name) {
  const intervalId = activeRunPolls.get(name);
  if (intervalId) {
    clearInterval(intervalId);
    activeRunPolls.set(name, null);
  }
}

async function pollRun(name) {
  try {
    const res = await fetch(
      `/api/method/cashew_integration.api.get_run_progress?run_name=${encodeURIComponent(name)}`,
      {
        method: 'GET',
        headers: {
          'X-Frappe-CSRF-Token': window.boot?.csrf_token || window.csrf_token || '',
        },
        credentials: 'same-origin',
      },
    );
    if (!res.ok) return;
    const json = await res.json();
    const data = json?.message;
    if (!data) return;
    const key = docKeyFor('Cashew Import Run', name);
    if (activeSubs.has(key)) {
      const payload = { doctype: 'Cashew Import Run', name, ...data };
      for (const cb of activeSubs.get(key)) cb(payload);
    }
  } catch (_e) {
    /* swallow — next tick retries */
  }
}
