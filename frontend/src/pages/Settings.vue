<script setup>
import { reactive, computed, onMounted } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { toast, createResource, frappeRequest } from 'frappe-ui';

import PageHeader from '@/components/shared/PageHeader.vue';
import SkeletonBlock from '@/components/shared/SkeletonBlock.vue';
import ConfirmDialog from '@/components/shared/ConfirmDialog.vue';

import AppearanceSection from '@/components/settings/AppearanceSection.vue';
import DefaultsSection from '@/components/settings/DefaultsSection.vue';
import MappingsSection from '@/components/settings/MappingsSection.vue';
import SaveBar from '@/components/settings/SaveBar.vue';
import ReadOnlyBanner from '@/components/settings/ReadOnlyBanner.vue';

import { hasWriteSettings } from '@/boot';
import { applyThemeFromDoc } from '@/theme';

const canWrite = hasWriteSettings();

const state = reactive({
  loading: true,
  saving: false,
  original: null,
  form: {
    accent_color: 'Indigo',
    accent_color_custom: '',
    company: null,
  },
});

const confirmState = reactive({
  open: false,
  title: '',
  body: '',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  kind: 'warning',
  resolver: null,
});

function confirmDialog({ title, body, confirmLabel, cancelLabel, kind = 'warning' }) {
  Object.assign(confirmState, {
    open: true,
    title,
    body,
    confirmLabel: confirmLabel || 'Confirm',
    cancelLabel: cancelLabel || 'Cancel',
    kind,
  });
  return new Promise((resolve) => { confirmState.resolver = resolve; });
}

function resolveConfirm(answer) {
  const r = confirmState.resolver;
  confirmState.resolver = null;
  confirmState.open = false;
  r?.(answer);
}

const isDirty = computed(() =>
  !!state.original &&
  (state.form.accent_color !== state.original.accent_color
    || (state.form.accent_color_custom || '') !== (state.original.accent_color_custom || '')
    || state.form.company !== state.original.company),
);

const settingsResource = createResource({
  url: 'frappe.client.get_value',
  cache: false,
  params: {
    doctype: 'Cashew Settings',
    filters: 'Cashew Settings',
    fieldname: ['accent_color', 'accent_color_custom', 'company'],
  },
  onSuccess: (data) => {
    const d = data || {};
    state.original = {
      accent_color: d.accent_color || 'Indigo',
      accent_color_custom: d.accent_color_custom || '',
      company: d.company || null,
    };
    state.form = { ...state.original };
    state.loading = false;
  },
  onError: () => { state.loading = false; },
});

onMounted(() => { settingsResource.fetch(); });

function onAccentChange(preset) {
  state.form.accent_color = preset;
  if (preset !== 'Custom') {
    applyThemeFromDoc({ accent_color: preset });
  } else if (isValidHex(state.form.accent_color_custom)) {
    applyThemeFromDoc({
      accent_color: 'Custom',
      accent_color_custom: state.form.accent_color_custom,
    });
  }
}

function onCustomHexChange(hex) {
  state.form.accent_color_custom = hex;
  if (state.form.accent_color === 'Custom' && isValidHex(hex)) {
    applyThemeFromDoc({ accent_color: 'Custom', accent_color_custom: hex });
  }
}

function isValidHex(s) {
  return /^#[0-9a-fA-F]{6}$/.test(s || '');
}

async function setValue(field, value) {
  await frappeRequest({
    url: 'frappe.client.set_value',
    method: 'POST',
    params: {
      doctype: 'Cashew Settings',
      name: 'Cashew Settings',
      fieldname: field,
      value: value ?? '',
    },
  });
}

async function onSave() {
  if (!canWrite || state.saving || !isDirty.value) return;
  state.saving = true;
  try {
    const writes = [];
    if (state.form.accent_color !== state.original.accent_color) {
      writes.push(setValue('accent_color', state.form.accent_color));
    }
    if ((state.form.accent_color_custom || '') !== (state.original.accent_color_custom || '')) {
      writes.push(setValue('accent_color_custom', state.form.accent_color_custom || ''));
    }
    if (state.form.company !== state.original.company) {
      writes.push(setValue('company', state.form.company || ''));
    }
    await Promise.all(writes);
    state.original = { ...state.form };
    toast.success('Settings saved');
  } catch (_e) {
    // c004 error interceptor already toasted
  } finally {
    state.saving = false;
  }
}

function onDiscard() {
  if (!state.original) return;
  state.form = { ...state.original };
  applyThemeFromDoc({
    accent_color: state.original.accent_color,
    accent_color_custom: state.original.accent_color_custom,
  });
}

onBeforeRouteLeave(async (to, from, next) => {
  if (!isDirty.value) return next();
  const ok = await confirmDialog({
    title: 'Leave settings?',
    body: 'You have unsaved changes. Leaving will discard them.',
    confirmLabel: 'Leave',
    cancelLabel: 'Stay',
    kind: 'warning',
  });
  if (ok) {
    applyThemeFromDoc({
      accent_color: state.original.accent_color,
      accent_color_custom: state.original.accent_color_custom,
    });
    next();
  } else {
    next(false);
  }
});
</script>

<template>
  <div class="px-4 md:px-6 py-6 max-w-3xl mx-auto pb-32">
    <PageHeader title="Settings" subtitle="Cashew preferences" :border="false" />

    <template v-if="state.loading">
      <SkeletonBlock class="h-24 mt-6" />
      <SkeletonBlock class="h-40 mt-4" />
      <SkeletonBlock class="h-24 mt-4" />
    </template>

    <template v-else>
      <ReadOnlyBanner v-if="!canWrite" class="mt-4" />

      <AppearanceSection
        :form="state.form"
        :disabled="!canWrite"
        @accent="onAccentChange"
        @custom-hex="onCustomHexChange"
        class="mt-6"
      />

      <DefaultsSection
        v-model:company="state.form.company"
        :disabled="!canWrite"
        class="mt-6"
      />

      <MappingsSection class="mt-6" />
    </template>

    <SaveBar
      v-if="canWrite && isDirty"
      :saving="state.saving"
      @save="onSave"
      @discard="onDiscard"
    />

    <ConfirmDialog
      :open="confirmState.open"
      :title="confirmState.title"
      :body="confirmState.body"
      :confirm-label="confirmState.confirmLabel"
      :cancel-label="confirmState.cancelLabel"
      :kind="confirmState.kind"
      @update:open="(v) => { if (!v) resolveConfirm(false); }"
      @confirm="resolveConfirm(true)"
      @cancel="resolveConfirm(false)"
    />
  </div>
</template>
