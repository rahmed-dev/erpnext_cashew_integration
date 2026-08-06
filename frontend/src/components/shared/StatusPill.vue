<script setup>
const props = defineProps({
  kind: { type: String, required: true }, // 'run-status' | 'row-validation' | 'row-revert' | 'txn-type' | 'source-type'
  value: { type: String, required: true },
  size: { type: String, default: 'md' },  // 'sm' | 'md'
  pulse: { type: Boolean, default: false },
});

const TABLES = {
  'run-status': {
    Draft:           { label: 'Draft',         cls: 'bg-gray-300 text-gray-700' },
    Parsed:          { label: 'Parsed',        cls: 'bg-sky-100 text-sky-700' },
    Validated:       { label: 'Validated',     cls: 'bg-blue-100 text-blue-700' },
    // In-flight states carry the accent (design philosophy #6) — hardcoded indigo
    // here stayed indigo after the user picked another accent in Settings.
    Queued:          { label: 'Queued',        cls: 'bg-cs-accent-100 text-cs-accent-700' },
    Processing:      { label: 'Processing',    cls: 'bg-cs-accent-100 text-cs-accent-700', pulse: true },
    Completed:       { label: 'Completed',     cls: 'bg-green-100 text-green-700' },
    Failed:          { label: 'Failed',        cls: 'bg-red-100 text-red-700' },
    Cancelled:       { label: 'Cancelled',     cls: 'bg-gray-200 text-gray-700' },
    Reverting:       { label: 'Reverting',     cls: 'bg-amber-100 text-amber-800', pulse: true },
    Reverted:        { label: 'Reverted',      cls: 'bg-amber-100 text-amber-800' },
    'Revert-Failed': { label: 'Revert Failed', cls: 'bg-red-100 text-red-800' },
  },
  'row-validation': {
    Valid:   { label: 'Valid',   cls: 'bg-green-100 text-green-700' },
    Error:   { label: 'Error',   cls: 'bg-red-100 text-red-700' },
    Skipped: { label: 'Skipped', cls: 'bg-gray-200 text-gray-700' },
  },
  // Fixed hues, not accent: these encode "is my ledger still what this row claims",
  // which must read the same under every accent preset. Split by severity —
  // red means the GL is gone and the row still claims it, sky/gray mean the app
  // corrected itself on purpose and the row is accounted for.
  'row-revert': {
    Reverted:               { label: 'Reverted',       cls: 'bg-amber-100 text-amber-800' },
    'Revert-Failed':        { label: 'Revert Failed',  cls: 'bg-red-100 text-red-800' },
    'Cancelled Externally': { label: 'Cancelled Outside', cls: 'bg-red-100 text-red-800' },
    'Deleted Externally':   { label: 'Deleted Outside',   cls: 'bg-red-100 text-red-800' },
    Resynced:               { label: 'Resynced',       cls: 'bg-sky-100 text-sky-800' },
    Superseded:             { label: 'Superseded',     cls: 'bg-gray-200 text-gray-600' },
  },
  'txn-type': {
    Income:              { label: 'Income',             cls: 'bg-green-50 text-green-700' },
    Expense:             { label: 'Expense',            cls: 'bg-red-50 text-red-700' },
    Transfer:            { label: 'Transfer',           cls: 'bg-slate-100 text-slate-700' },
    'External Transfer': { label: 'External Transfer',  cls: 'bg-slate-100 text-slate-700' },
    Adjustment:          { label: 'Adjustment',         cls: 'bg-yellow-50 text-yellow-800' },
    'Loan Receivable':   { label: 'Loan Receivable',    cls: 'bg-violet-100 text-violet-700' },
    'Loan Payable':      { label: 'Loan Payable',       cls: 'bg-violet-100 text-violet-700' },
  },
  // Deliberately NOT accent-tinted: CSV and SQLite render side by side, and under
  // the Monochrome preset --cs-accent-100 (#e5e7eb) is nearly CSV's gray (#f3f4f6),
  // so accent here would trade a theming bug for an unreadable one. A fixed hue
  // stays distinct from gray under every accent.
  'source-type': {
    CSV:    { label: 'CSV',    cls: 'bg-gray-100 text-gray-700' },
    SQLite: { label: 'SQLite', cls: 'bg-violet-100 text-violet-700' },
  },
};

function entry() {
  const table = TABLES[props.kind] || {};
  return table[props.value] || { label: props.value, cls: 'bg-gray-100 text-gray-700' };
}
</script>

<template>
  <span
    v-if="entry().label"
    :class="[
      'inline-flex items-center rounded-full font-medium tabular-nums',
      size === 'sm' ? 'px-2 py-0.5 text-[12px] leading-[18px]' : 'px-2.5 py-0.5 text-[13px] leading-[20px]',
      entry().cls,
      (pulse || entry().pulse) ? 'animate-pulse' : '',
    ]"
    :aria-label="`${kind}: ${entry().label}`"
  >{{ entry().label }}</span>
</template>
