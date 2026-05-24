// f010 c006-b — bulk action registry (D11).

export const BULK_ACTIONS = [
  {
    id: 'set_party',
    label: 'Set party…',
    enabledWhen: ({ selectedRows, editable }) => editable && selectedRows.length > 0,
    openModal: 'BulkPartyModal',
  },
  {
    id: 'revalidate_selected',
    label: 'Re-validate selected',
    enabledWhen: ({ selectedRows, editable }) => editable && selectedRows.length > 0,
    method: 'row_explorer_revalidate',
    extractParams: ({ runName, selectedRows }) => ({
      run_name: runName,
      row_indices: selectedRows.map((r) => r.row_idx),
    }),
    toast: ({ selectedRows }) => `Re-validated ${selectedRows.length} row${selectedRows.length === 1 ? '' : 's'}.`,
  },
];
