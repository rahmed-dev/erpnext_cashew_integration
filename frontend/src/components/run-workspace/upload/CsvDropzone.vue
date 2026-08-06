<script setup>
import { ref, computed } from 'vue';
import { toast } from 'frappe-ui';
import { Upload, FileText, X } from 'lucide-vue-next';

const props = defineProps({
  modelValue: { type: [String, null], default: null },
  disabled: { type: Boolean, default: false },
  // f011 c005 — 'CSV' | 'SQLite'. Widens accept + relabels; upload mechanics unchanged.
  sourceType: { type: String, default: 'CSV' },
});
const emit = defineEmits(['update:modelValue']);

const fileInfo = ref(null);
const hover = ref(false);
const uploading = ref(false);

// Extensions are the authority — the browser-reported MIME for these files is
// unreliable (Android hands us text/plain or application/octet-stream for a .csv;
// SQLite has no registered MIME or iOS UTI at all). The MIME entries below are
// picker hints only; onFile() enforces the extension.
const EXT_CSV = ['.csv'];
const EXT_SQLITE = ['.sql', '.sqlite', '.db'];
const ACCEPT_CSV = [...EXT_CSV, 'text/csv', 'text/plain', 'application/vnd.ms-excel'];
const ACCEPT_SQLITE = [
  ...EXT_SQLITE,
  'application/x-sqlite3',
  'application/vnd.sqlite3',
  'application/octet-stream',
];
// 50 MB is ample (a 553-txn Cashew DB is ~KBs). Bump here if a larger backup ever fails.
const MAX_BYTES = 50 * 1024 * 1024;

// iOS Files and some Android pickers grey out every entry when `accept` contains an
// extension they cannot map to a known type — .sqlite/.db always, .csv often. On such
// devices we send no `accept` at all and rely on the extension check in onFile().
const isCoarsePointer =
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(pointer: coarse)').matches;

const picker = ref(null);

const isSqlite = computed(() => props.sourceType === 'SQLite');
const allowedExts = computed(() => (isSqlite.value ? EXT_SQLITE : EXT_CSV));
const acceptAttr = computed(() => {
  if (isCoarsePointer) return undefined;
  return (isSqlite.value ? ACCEPT_SQLITE : ACCEPT_CSV).join(',');
});
const hintCopy = computed(() => (isSqlite.value ? 'SQLite backup up to 50 MB' : 'CSV up to 50 MB'));

function pickFile() {
  if (props.disabled || uploading.value) return;
  picker.value?.click();
}

function hasAllowedExt(name) {
  const lower = (name || '').toLowerCase();
  return allowedExts.value.some((ext) => lower.endsWith(ext));
}

async function onFile(file) {
  if (!file) return;
  if (!hasAllowedExt(file.name)) {
    toast.error(`Select a ${allowedExts.value.join(' / ')} file.`);
    return;
  }
  if (file.size > MAX_BYTES) {
    toast.error('File must be under 50 MB.');
    return;
  }
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('is_private', '1');
    const res = await fetch('/api/method/upload_file', {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': window.boot?.csrf_token || window.csrf_token || '' },
      credentials: 'same-origin',
      body: fd,
    });
    const json = await res.json();
    if (!res.ok || !json?.message?.file_url) {
      throw new Error(json?.exception || 'Upload failed');
    }
    fileInfo.value = { name: file.name, size: file.size, url: json.message.file_url };
    emit('update:modelValue', json.message.file_url);
  } catch (e) {
    toast.error(e?.message || 'Could not upload file.');
  } finally {
    uploading.value = false;
  }
}

function onInputChange(ev) {
  const f = ev.target.files?.[0];
  onFile(f);
  ev.target.value = '';
}

function onDrop(ev) {
  ev.preventDefault();
  hover.value = false;
  const f = ev.dataTransfer?.files?.[0];
  if (f) onFile(f);
}

function clearFile() {
  fileInfo.value = null;
  emit('update:modelValue', null);
}
</script>

<template>
  <div>
    <!-- Kept OUTSIDE the dropzone: a click dispatched on an input nested inside the
         dropzone bubbles back to its @click handler and re-opens the picker, which
         mobile browsers abort. Visually hidden rather than display:none — iOS Safari
         ignores programmatic .click() on a display:none input. -->
    <input
      id="cashew-csv-picker"
      ref="picker"
      type="file"
      :accept="acceptAttr"
      class="sr-only absolute w-px h-px overflow-hidden"
      tabindex="-1"
      aria-hidden="true"
      @change="onInputChange"
    />

    <div
      v-if="!fileInfo"
      :class="[
        'rounded-lg border-2 border-dashed p-6 flex flex-col items-center justify-center gap-2 text-center cursor-pointer',
        hover ? 'border-[var(--cs-accent)] bg-[var(--cs-accent-50)]' : 'border-gray-300 bg-gray-50 hover:border-gray-400',
        disabled && 'opacity-50 cursor-not-allowed',
      ]"
      role="button"
      tabindex="0"
      @click="pickFile"
      @dragover.prevent="hover = true"
      @dragleave="hover = false"
      @drop="onDrop"
      @keypress.enter="pickFile"
    >
      <Upload :size="22" class="text-gray-500" />
      <div class="text-sm text-gray-700">
        <span class="font-medium text-[var(--cs-accent)]">Click to upload</span> or drag and drop
      </div>
      <div class="text-xs text-gray-500">{{ hintCopy }}</div>
    </div>

    <div v-else class="flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-2 bg-white">
      <span class="inline-flex items-center justify-center w-8 h-8 bg-[var(--cs-accent-50)] text-[var(--cs-accent)] rounded">
        <FileText :size="16" />
      </span>
      <div class="flex-1 min-w-0">
        <div class="text-sm text-gray-900 truncate">{{ fileInfo.name }}</div>
        <div class="text-xs text-gray-500">{{ (fileInfo.size / 1024).toFixed(1) }} KB</div>
      </div>
      <button
        type="button"
        class="h-7 w-7 rounded hover:bg-gray-100 flex items-center justify-center text-gray-500"
        aria-label="Remove file"
        :disabled="disabled"
        @click="clearFile"
      >
        <X :size="14" />
      </button>
    </div>
  </div>
</template>
