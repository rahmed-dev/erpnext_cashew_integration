<script setup>
import { ref } from 'vue';
import { toast } from 'frappe-ui';
import { Upload, FileText, X } from 'lucide-vue-next';

const props = defineProps({
  modelValue: { type: [String, null], default: null },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const fileInfo = ref(null);
const hover = ref(false);
const uploading = ref(false);

const ACCEPT = ['text/csv', 'application/vnd.ms-excel'];
const MAX_BYTES = 50 * 1024 * 1024;

function pickFile() {
  if (props.disabled || uploading.value) return;
  document.getElementById('cashew-csv-picker')?.click();
}

async function onFile(file) {
  if (!file) return;
  if (file.size > MAX_BYTES) {
    toast.error('CSV must be under 50 MB.');
    return;
  }
  uploading.value = true;
  try {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('is_private', '1');
    fd.append('folder', 'Home/Cashew Imports');
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
      <div class="text-xs text-gray-500">CSV up to 50 MB</div>
      <input
        id="cashew-csv-picker"
        type="file"
        :accept="ACCEPT.join(',')"
        class="hidden"
        @change="onInputChange"
      />
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
