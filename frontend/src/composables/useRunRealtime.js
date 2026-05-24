// f010 c006 — per-run realtime hookup via c008's subscribeDoc.
import { watch, onBeforeUnmount } from 'vue';
import { subscribeDoc } from '@/realtime';

export function useRunRealtime(runName, { patchDoc, patchRow }) {
  let unsub = null;

  function disconnect() {
    unsub?.();
    unsub = null;
  }

  watch(
    runName,
    (n) => {
      disconnect();
      if (!n) return;
      unsub = subscribeDoc('Cashew Import Run', n, (event) => {
        if (!event) return;
        const doc = event.doc || (event.name ? event : null);
        if (doc && typeof patchDoc === 'function') patchDoc(doc);
        if (event.rows && Array.isArray(event.rows) && typeof patchRow === 'function') {
          for (const r of event.rows) patchRow(r.row_idx, r);
        }
        if (event.row && typeof patchRow === 'function') {
          patchRow(event.row.row_idx, event.row);
        }
      });
    },
    { immediate: true },
  );

  onBeforeUnmount(disconnect);
}
