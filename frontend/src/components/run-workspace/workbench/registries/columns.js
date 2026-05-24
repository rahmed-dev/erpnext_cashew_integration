// f010 c006-b — column registry (D11).
// Each column def → renderer string; RowsTable maps renderer to cell template.

export const COLUMN_DEFS = [
  { id: 'select',          header: '',         field: '_select',          renderer: 'select-checkbox', widthPx: 32,  sticky: 'left' },
  { id: 'row_idx',         header: '#',        field: 'row_idx',          renderer: 'text',            align: 'right', tabular: true, sticky: 'left', sortable: true },
  { id: 'validation',      header: 'Status',   field: 'validation_status', renderer: 'validation-pill', sortable: true },
  { id: 'txn_date',        header: 'Date',     field: 'txn_date',         renderer: 'date-short',      sortable: true },
  { id: 'raw_account',     header: 'Account',  field: 'raw_account',      renderer: 'text' },
  { id: 'amount',          header: 'Amount',   field: 'base_amount',      renderer: 'amount-signed',  align: 'right', tabular: true, sortable: true, currencyField: 'company_currency' },
  { id: 'txn_type',        header: 'Type',     field: 'txn_type',         renderer: 'type-pill',      sortable: true },
  { id: 'category',        header: 'Category', field: 'category',         renderer: 'category-with-sub', subField: 'sub_category', sortable: true },
  { id: 'note',            header: 'Note',     field: 'note',             renderer: 'truncated' },
  { id: 'resolved_party',  header: 'Party',    field: 'resolved_party',   renderer: 'party-edit' },
  { id: 'resolved_account',header: 'GL Account', field: 'resolved_account', renderer: 'text' },
  { id: 'error_message',   header: 'Error',    field: 'validation_error_message', renderer: 'error-text' },
  { id: 'posted',          header: 'Posted',   field: 'posted_docname',   renderer: 'posted-link' },
  { id: 'revert',          header: 'Revert',   field: 'revert_status',    renderer: 'revert-pill', errorField: 'revert_error' },
  { id: 'kebab',           header: '',         field: '_kebab',           renderer: 'row-kebab', widthPx: 40, sticky: 'right' },
];

export const COLUMN_PRESETS = {
  'Validation-focused': [
    'select', 'row_idx', 'validation', 'txn_date', 'raw_account',
    'amount', 'txn_type', 'category', 'resolved_party', 'error_message', 'kebab',
  ],
  'Posting-focused': [
    'select', 'row_idx', 'validation', 'txn_date', 'amount', 'txn_type',
    'category', 'resolved_party', 'resolved_account', 'posted', 'revert', 'kebab',
  ],
  'Compact': [
    'select', 'row_idx', 'validation', 'txn_date', 'amount', 'txn_type', 'category', 'kebab',
  ],
  'All': COLUMN_DEFS.map((c) => c.id),
};

export function pickInitialPreset(rows = []) {
  if (rows.some((r) => r.validation_status === 'Error')) return 'Validation-focused';
  if (rows.some((r) => r.posted_docname)) return 'Posting-focused';
  return 'Compact';
}

export function colDef(id) {
  return COLUMN_DEFS.find((c) => c.id === id);
}
