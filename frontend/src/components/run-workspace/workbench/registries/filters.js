// f010 c006-b — declarative filter facet registry (D11).

export const FILTER_FACETS = [
  {
    id: 'validation_status',
    label: 'Validation Status',
    type: 'select',
    options: ['Valid', 'Error', 'Skipped'],
    apply: (row, value) => !value?.length || value.includes(row.validation_status),
    chipLabel: (v) => `Status: ${Array.isArray(v) ? v.join(', ') : v}`,
  },
  {
    id: 'txn_type',
    label: 'Transaction Type',
    type: 'select',
    options: ['Income', 'Expense', 'Transfer', 'External Transfer', 'Adjustment', 'Loan Receivable', 'Loan Payable'],
    apply: (row, value) => !value?.length || value.includes(row.txn_type),
    chipLabel: (v) => `Type: ${Array.isArray(v) ? v.join(', ') : v}`,
  },
  {
    id: 'category',
    label: 'Category',
    type: 'string-facet',
    optionsFrom: 'rows.category',
    apply: (row, value) => !value?.length || value.includes(row.category),
    chipLabel: (v) => `Category: ${Array.isArray(v) ? v.join(', ') : v}`,
  },
  {
    id: 'raw_account',
    label: 'Raw Account',
    type: 'string-facet',
    optionsFrom: 'rows.raw_account',
    apply: (row, value) => !value?.length || value.includes(row.raw_account),
    chipLabel: (v) => `Account: ${Array.isArray(v) ? v.join(', ') : v}`,
  },
  {
    id: 'has_party',
    label: 'Party',
    type: 'tri-state',
    options: ['Set', 'Missing'],
    apply: (row, value) => {
      if (!value) return true;
      if (value === 'Set') return !!row.resolved_party;
      if (value === 'Missing') return !row.resolved_party;
      return true;
    },
    chipLabel: (v) => `Party: ${v}`,
  },
  {
    id: 'is_duplicate',
    label: 'Duplicates',
    type: 'tri-state',
    options: ['Only', 'Hide'],
    apply: (row, value) => {
      if (!value) return true;
      if (value === 'Only') return !!row.is_duplicate;
      if (value === 'Hide') return !row.is_duplicate;
      return true;
    },
    chipLabel: (v) => `Duplicates: ${v}`,
  },
  {
    id: 'posted',
    label: 'Posted',
    type: 'tri-state',
    options: ['Only', 'Hide'],
    apply: (row, value) => {
      if (!value) return true;
      if (value === 'Only') return !!row.posted_docname;
      if (value === 'Hide') return !row.posted_docname;
      return true;
    },
    chipLabel: (v) => `Posted: ${v}`,
  },
];

const SEARCHABLE_FIELDS = ['row_idx', 'raw_account', 'amount', 'base_amount', 'txn_type', 'category', 'sub_category', 'note', 'resolved_party', 'resolved_account', 'validation_error_message'];

export function applyFilters(rows, filters, search) {
  const terms = (search || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
  return rows.filter((row) => {
    for (const facet of FILTER_FACETS) {
      const value = filters?.[facet.id];
      if (!facet.apply(row, value)) return false;
    }
    if (terms.length === 0) return true;
    const haystack = SEARCHABLE_FIELDS.map((f) => String(row[f] ?? '').toLowerCase()).join(' ');
    return terms.every((t) => haystack.includes(t));
  });
}
