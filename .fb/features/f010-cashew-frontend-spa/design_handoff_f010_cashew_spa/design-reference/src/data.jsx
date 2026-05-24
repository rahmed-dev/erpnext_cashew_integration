// Cashew SPA — mock data, PKR. Realistic-ish for a Pakistani SMB doing monthly imports.
// Exposed on window so each artboard module can read it.

const CURRENCY = 'PKR';

// PKR formatter — Pakistan uses Western grouping (1,234,567.89)
const fmtPKR = (n, { signed = false, compact = false, currency = CURRENCY } = {}) => {
  if (n == null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  const sign = signed ? (n > 0 ? '+' : n < 0 ? '−' : '') : (n < 0 ? '−' : '');
  if (compact) {
    if (abs >= 10_000_000) return `${sign}Rs ${(abs/10_000_000).toFixed(1)}Cr`;
    if (abs >= 100_000)    return `${sign}Rs ${(abs/100_000).toFixed(1)}L`;
    if (abs >= 1_000)      return `${sign}Rs ${(abs/1_000).toFixed(1)}K`;
  }
  const formatted = new Intl.NumberFormat('en-PK', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(abs);
  return `${sign}Rs ${formatted}`;
};

// Relative time
const relTime = (iso) => {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 86400*7) return `${Math.floor(diff/86400)}d ago`;
  return d.toLocaleDateString('en-PK', { month: 'short', day: 'numeric', year: 'numeric' });
};

const fmtDate = (iso, fmt = 'short') => {
  const d = new Date(iso);
  if (fmt === 'short')  return d.toLocaleDateString('en-PK', { month: 'short', day: 'numeric' });
  if (fmt === 'medium') return d.toLocaleDateString('en-PK', { month: 'short', day: 'numeric', year: 'numeric' });
  return d.toLocaleDateString('en-PK', { month: 'long', day: 'numeric', year: 'numeric' });
};

const fmtRange = (a, b) => `${fmtDate(a, 'short')} – ${fmtDate(b, 'medium')}`;

// ── Dashboard ─────────────────────────────────────────────────────────────
const DASHBOARD = {
  period: { start: '2026-05-01', end: '2026-05-24' },
  currency: 'PKR',
  income_total: 4_245_000,
  expense_total: 2_867_350,
  income_by_category: [
    { category: 'Consulting Revenue', amount: 2_400_000 },
    { category: 'Salary Reimburse',   amount:   850_000 },
    { category: 'Equity Dividend',    amount:   620_000 },
    { category: 'Interest',           amount:   265_000 },
    { category: 'Refunds',            amount:   110_000 },
  ],
  expense_by_category: [
    { category: 'Office Rent',        amount:   780_000 },
    { category: 'Salaries (Contract)',amount:   720_000 },
    { category: 'Cloud & Tools',      amount:   412_000 },
    { category: 'Travel',             amount:   356_000 },
    { category: 'Utilities',          amount:   188_500 },
    { category: 'Marketing',          amount:   165_000 },
  ],
  balance_tiles: {
    cash_bank:        { amount: 12_485_000, prior_amount: 11_180_000 },
    receivable:       { amount:  3_240_000, prior_amount:  3_810_000 },
    payable:          { amount:  1_125_000, prior_amount:    960_000 },
    net_for_period:   { amount:  1_377_650 },
  },
  recent_runs: [
    { name: 'CSH-IMP-2026-000017', status: 'Completed',  period_start: '2026-04-01', period_end: '2026-04-30', rows_total: 126, rows_valid: 124, rows_failed: 2, rows_posted: 124, rows_skipped: 0, modified: '2026-05-02T09:14:22' },
    { name: 'CSH-IMP-2026-000016', status: 'Processing', period_start: '2026-05-01', period_end: '2026-05-24', rows_total: 98,  rows_valid: 91,  rows_failed: 0, rows_posted: 47,  rows_skipped: 0, modified: '2026-05-24T08:02:00' },
    { name: 'CSH-IMP-2026-000015', status: 'Failed',     period_start: '2026-03-01', period_end: '2026-03-31', rows_total: 142, rows_valid: 118, rows_failed: 24,rows_posted:   0, rows_skipped: 0, modified: '2026-04-04T17:48:00' },
    { name: 'CSH-IMP-2026-000014', status: 'Reverted',   period_start: '2026-02-01', period_end: '2026-02-28', rows_total: 102, rows_valid: 102, rows_failed: 0, rows_posted: 102, rows_skipped: 0, modified: '2026-03-12T11:22:00' },
    { name: 'CSH-IMP-2026-000013', status: 'Completed',  period_start: '2026-01-01', period_end: '2026-01-31', rows_total: 88,  rows_valid:  88, rows_failed: 0, rows_posted:  88, rows_skipped: 0, modified: '2026-02-04T10:00:00' },
  ],
};

// ── Imports List ──────────────────────────────────────────────────────────
const RUNS_LIST = [
  ...DASHBOARD.recent_runs.map(r => ({ ...r, company: 'Karachi Trading Co.' })),
  { name: 'CSH-IMP-2025-000012', status: 'Completed',  company: 'Karachi Trading Co.', period_start: '2025-12-01', period_end: '2025-12-31', rows_total:  79, rows_valid:  79, rows_failed: 0, rows_posted:  79, rows_skipped: 0, modified: '2026-01-03T08:14:00' },
  { name: 'CSH-IMP-2025-000011', status: 'Cancelled',  company: 'Karachi Trading Co.', period_start: '2025-11-01', period_end: '2025-11-30', rows_total: 110, rows_valid:  98, rows_failed: 0, rows_posted:   0, rows_skipped:12, modified: '2025-12-05T14:30:00' },
  { name: 'CSH-IMP-2025-000010', status: 'Completed',  company: 'Karachi Trading Co.', period_start: '2025-10-01', period_end: '2025-10-31', rows_total:  91, rows_valid:  91, rows_failed: 0, rows_posted:  91, rows_skipped: 0, modified: '2025-11-04T09:14:00' },
  { name: 'CSH-IMP-2025-000009', status: 'Revert-Failed', company: 'Karachi Trading Co.', period_start: '2025-09-01', period_end: '2025-09-30', rows_total: 134, rows_valid: 134, rows_failed: 0, rows_posted: 134, rows_skipped: 0, modified: '2025-10-08T16:00:00' },
  { name: 'CSH-IMP-2025-000008', status: 'Completed',  company: 'Karachi Trading Co.', period_start: '2025-08-01', period_end: '2025-08-31', rows_total: 102, rows_valid: 102, rows_failed: 0, rows_posted: 102, rows_skipped: 0, modified: '2025-09-02T11:00:00' },
  { name: 'CSH-IMP-2025-000007', status: 'Completed',  company: 'Karachi Trading Co.', period_start: '2025-07-01', period_end: '2025-07-31', rows_total:  87, rows_valid:  87, rows_failed: 0, rows_posted:  87, rows_skipped: 0, modified: '2025-08-04T10:00:00' },
];

// ── Run Rows (workbench) ──────────────────────────────────────────────────
// Mix of valid/error/posted to make the workbench interesting.
const PARTIES = ['ACME Pvt Ltd', 'Bashir Bros.', 'Saima Enterprises', 'NetSol Tech', 'Indus Motor Co.', 'PTCL', 'K-Electric', 'Mehran Foods', 'CityFiber'];
const ACCOUNTS = ['Office Rent - KTC', 'Cloud Services - KTC', 'Salary Payable - KTC', 'Bank - HBL Main - KTC', 'Bank - Meezan - KTC', 'Petty Cash - KTC', 'Travel Expenses - KTC', 'Utilities - Electricity - KTC', 'Utilities - Internet - KTC', 'Receivable - Trade - KTC', 'Sales Revenue - KTC', 'Consulting Income - KTC'];

const ROW_TEMPLATES = [
  { txn_type: 'Expense',  category: 'Office Rent',     sub_category: 'Karachi HQ',     raw_account: 'HBL Main',     resolved_account: 'Office Rent - KTC',          base_amount: -780_000, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Expense',  category: 'Cloud & Tools',   sub_category: 'AWS',             raw_account: 'HBL Main',     resolved_account: 'Cloud Services - KTC',       base_amount: -184_500, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Expense',  category: 'Salaries',        sub_category: 'Contract',        raw_account: 'HBL Main',     resolved_account: 'Salary Payable - KTC',       base_amount: -720_000, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Income',   category: 'Consulting Revenue', sub_category: 'NetSol Q2',    raw_account: 'HBL Main',     resolved_account: 'Consulting Income - KTC',    base_amount: 1_200_000, income_flag:  1, validation_status: 'Valid', resolved_party_type: 'Customer', resolved_party: 'NetSol Tech' },
  { txn_type: 'Expense',  category: 'Travel',          sub_category: 'Air ticket',      raw_account: 'Card - HBL',   resolved_account: 'Travel Expenses - KTC',      base_amount:  -98_400, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Expense',  category: 'Utilities',       sub_category: 'Electricity',     raw_account: 'HBL Main',     resolved_account: 'Utilities - Electricity - KTC', base_amount: -42_300, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Transfer', category: 'Inter-bank',      sub_category: 'HBL → Meezan',    raw_account: 'HBL Main',     resolved_account: 'Bank - HBL Main - KTC',      resolved_external_account: 'Bank - Meezan - KTC',  base_amount: -500_000, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Income',   category: 'Refunds',         sub_category: 'Vendor refund',   raw_account: 'HBL Main',     resolved_account: 'Sales Revenue - KTC',        base_amount:   12_500, income_flag:  1, validation_status: 'Valid' },
  // ERROR rows
  { txn_type: 'Expense',  category: 'Marketing',       sub_category: 'Google Ads',      raw_account: 'Card - HBL',   resolved_account: null,                         base_amount:  -64_800, income_flag: -1, validation_status: 'Error', validation_error_code: 'NO_ACCOUNT_MAP', validation_error_message: 'No account mapping found for raw account "Card - HBL" with category "Marketing".' },
  { txn_type: 'Expense',  category: 'Office Supplies', sub_category: 'Stationery',      raw_account: 'Petty Cash',   resolved_account: 'Petty Cash - KTC',           base_amount:   -3_200, income_flag: -1, validation_status: 'Error', validation_error_code: 'MISSING_PARTY', validation_error_message: 'Supplier account requires a party. Set "Bashir Bros." or similar.' },
  { txn_type: 'Income',   category: 'Consulting Revenue', sub_category: 'ACME Apr',     raw_account: 'HBL Main',     resolved_account: 'Consulting Income - KTC',    base_amount:  900_000, income_flag:  1, validation_status: 'Error', validation_error_code: 'MISSING_PARTY', validation_error_message: 'Customer party not resolved. Hint: "ACME Pvt Ltd" exists.' },
  { txn_type: 'Transfer', category: 'Inter-bank',      sub_category: 'Meezan → HBL',    raw_account: 'Meezan Save',  resolved_account: 'Bank - Meezan - KTC',        resolved_external_account: null,                   base_amount: -250_000, income_flag: -1, validation_status: 'Error', validation_error_code: 'NO_EXTERNAL_ACCT', validation_error_message: 'Transfer row missing destination account.' },
  { txn_type: 'Expense',  category: 'Travel',          sub_category: 'Uber',            raw_account: 'Card - HBL',   resolved_account: null,                         base_amount:   -2_400, income_flag: -1, validation_status: 'Skipped' },
  // More valid rows
  { txn_type: 'Income',   category: 'Equity Dividend', sub_category: 'Indus Motor',     raw_account: 'HBL Main',     resolved_account: 'Sales Revenue - KTC',        base_amount:  620_000, income_flag:  1, validation_status: 'Valid' },
  { txn_type: 'Expense',  category: 'Utilities',       sub_category: 'Internet',        raw_account: 'HBL Main',     resolved_account: 'Utilities - Internet - KTC', base_amount:  -18_900, income_flag: -1, validation_status: 'Valid', resolved_party_type: 'Supplier', resolved_party: 'PTCL' },
  { txn_type: 'Income',   category: 'Interest',        sub_category: 'Term deposit',    raw_account: 'HBL Main',     resolved_account: 'Sales Revenue - KTC',        base_amount:   78_400, income_flag:  1, validation_status: 'Valid' },
  { txn_type: 'Expense',  category: 'Cloud & Tools',   sub_category: 'Linear',          raw_account: 'Card - HBL',   resolved_account: 'Cloud Services - KTC',       base_amount:   -8_200, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Loan Payable', category: 'Loan',        sub_category: 'Vehicle EMI',     raw_account: 'HBL Main',     resolved_account: 'Salary Payable - KTC',       base_amount:  -45_000, income_flag: -1, validation_status: 'Valid', resolved_party_type: 'Supplier', resolved_party: 'Indus Motor Co.' },
  { txn_type: 'Adjustment', category: 'Bank fees',     sub_category: 'Monthly charges', raw_account: 'HBL Main',     resolved_account: 'Cloud Services - KTC',       base_amount:   -1_250, income_flag: -1, validation_status: 'Valid' },
  { txn_type: 'Income',   category: 'Consulting Revenue', sub_category: 'ACME May',     raw_account: 'HBL Main',     resolved_account: 'Consulting Income - KTC',    base_amount:  300_000, income_flag:  1, validation_status: 'Valid', resolved_party_type: 'Customer', resolved_party: 'ACME Pvt Ltd' },
];

// Expand into ~36 rows w/ unique idx + date so the workbench feels populated
const ROWS = [];
{
  let idx = 1;
  const startDay = 1;
  for (let i = 0; i < 36; i++) {
    const tmpl = ROW_TEMPLATES[i % ROW_TEMPLATES.length];
    const day = startDay + Math.floor(i * 0.7);
    const date = `2026-05-${String(Math.min(28, day)).padStart(2,'0')}`;
    ROWS.push({
      row_idx: idx++,
      txn_date: date,
      raw_txn_time: `${10 + (i % 8)}:${String((i*7) % 60).padStart(2,'0')}`,
      source_currency: 'PKR',
      company_currency: 'PKR',
      raw_amount: tmpl.base_amount,
      exchange_rate: 1,
      is_duplicate: i === 22, // one duplicate
      posted_doctype: null,
      posted_docname: null,
      posted_gl_date: null,
      revert_status: null,
      ...tmpl,
    });
  }
}

// ── Helpers exposed globally ──────────────────────────────────────────────
Object.assign(window, {
  CASHEW_DATA: { DASHBOARD, RUNS_LIST, ROWS },
  fmtPKR, fmtDate, fmtRange, relTime,
});
