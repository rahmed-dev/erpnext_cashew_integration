// f010 c006 — reactive Cashew Import Run + rows fetch via frappe.client.get.
import { ref } from 'vue';
import { createResource } from 'frappe-ui';

export function useRun(runName) {
  const doc = ref(null);
  const rows = ref([]);
  const loading = ref(true);
  const error = ref(null);

  const resource = createResource({
    url: 'frappe.client.get',
    cache: false,
    makeParams: () => ({
      doctype: 'Cashew Import Run',
      name: runName.value,
    }),
    auto: false,
    onSuccess: (data) => {
      doc.value = data;
      rows.value = data?.import_rows || [];
      loading.value = false;
      error.value = null;
    },
    onError: (err) => {
      error.value = err;
      loading.value = false;
    },
  });

  function reload() {
    if (!runName.value) {
      doc.value = null;
      rows.value = [];
      loading.value = false;
      return;
    }
    loading.value = true;
    resource.reload();
  }

  function patchDoc(patch) {
    if (!doc.value || !patch) return;
    doc.value = { ...doc.value, ...patch };
  }

  function patchRow(rowIdx, patch) {
    if (!patch) return;
    const i = rows.value.findIndex((r) => r.row_idx === rowIdx);
    if (i === -1) return;
    rows.value.splice(i, 1, { ...rows.value[i], ...patch });
  }

  function replaceAllRows(newRows) {
    rows.value = newRows || [];
  }

  return { doc, rows, loading, error, reload, patchDoc, patchRow, replaceAllRows };
}
