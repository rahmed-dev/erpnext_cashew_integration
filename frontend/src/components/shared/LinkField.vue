<script setup>
/*
 * LinkField — canonical link/reference picker for the cashew SPA.
 *
 * frappe-ui <Autocomplete> only CLIENT-FILTERS the :options array you pass it;
 * it does NOT self-fetch from a `reference_doctype` prop (that prop is a no-op).
 * This wrapper feeds it server results: every keystroke (debounced) hits
 * `frappe.desk.search.search_link`, which honors any get_query / standard_queries
 * registered for that doctype — the same code path the Desk Link field uses.
 * See CLAUDE.md "SPA API discipline" rule 2.
 */
import { ref, watch } from 'vue';
import { Autocomplete, frappeRequest } from 'frappe-ui';

const props = defineProps({
  modelValue: { type: [String, null], default: '' },
  doctype: { type: String, required: true },
  placeholder: { type: String, default: '' },
  // Optional Frappe filters dict forwarded to search_link, e.g. { is_group: 0 }.
  filters: { type: Object, default: null },
  pageLength: { type: Number, default: 20 },
});
const emit = defineEmits(['update:modelValue']);

const options = ref([]);
const loading = ref(false);
let seq = 0;
let timer = null;

function toOption(v, description) {
  return { label: v, value: v, description: description || '' };
}

async function fetchOptions(txt) {
  const mine = ++seq;
  loading.value = true;
  try {
    const rows = await frappeRequest({
      url: 'frappe.desk.search.search_link',
      params: {
        doctype: props.doctype,
        txt: txt || '',
        page_length: props.pageLength,
        ...(props.filters ? { filters: JSON.stringify(props.filters) } : {}),
      },
    });
    if (mine !== seq) return; // a newer keystroke already won
    const list = Array.isArray(rows) ? rows : [];
    options.value = list.map((r) => toOption(r.value, r.description));
  } catch (_e) {
    if (mine === seq) options.value = [];
  } finally {
    if (mine === seq) loading.value = false;
  }
}

function onQuery(txt) {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => fetchOptions(txt), 250);
}

function onSelect(opt) {
  const v = typeof opt === 'string' ? opt : (opt?.value ?? opt?.name ?? '');
  // Keep the chosen row available so its label renders even before next search.
  if (v && !options.value.some((o) => o.value === v)) {
    options.value = [toOption(v), ...options.value];
  }
  emit('update:modelValue', v);
}

// Seed the list with the current value so the selected label shows on open.
watch(
  () => [props.modelValue, props.doctype],
  () => {
    if (props.modelValue && !options.value.some((o) => o.value === props.modelValue)) {
      options.value = [toOption(props.modelValue), ...options.value];
    }
  },
  { immediate: true },
);

// Fetch-on-focus: every time the field gains focus, prime a top-N list so the
// dropdown is never blank before the user types (Desk Link fields behave the same).
// frappe-ui <Autocomplete> does NOT self-fetch, so without this the list stays empty
// until the first keystroke. focusin bubbles up from the inner ComboboxInput.
function onFocus() {
  fetchOptions('');
}

// When the doctype changes (e.g. party_type Customer→Supplier) the old options are
// stale — drop them so the next focus re-primes for the new doctype.
watch(
  () => props.doctype,
  (dt, prev) => {
    if (dt === prev) return;
    options.value = props.modelValue ? [toOption(props.modelValue)] : [];
  },
);
</script>

<template>
  <!-- focusin bubbles from the inner ComboboxInput, so the wrapper catches first
       focus and primes the list (Autocomplete exposes no focus event of its own). -->
  <div @focusin="onFocus">
    <Autocomplete
      :modelValue="modelValue"
      :options="options"
      :placeholder="placeholder"
      :loading="loading"
      @update:query="onQuery"
      @update:modelValue="onSelect"
    />
  </div>
</template>
