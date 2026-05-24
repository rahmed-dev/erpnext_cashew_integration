# c012 — settings-page

> **Type:** ui-page
> **Depends on:** c004 (shell + boot accessors + ThemeController),
> c013 (schema additions — `Cashew Settings.accent_color` + `.accent_color_custom`)
> **Arch refs:** D5 (hybrid API), D6 (theme is explicitly persisted —
> the one carve-out from session-only state), D12 (Settings page added
> as 4th surface), D13 / D13–D14 Amendment 1 (Custom hex escape hatch)
> **Design brief:** `.fb/ui/pages/settings.md` (note: brief predates
> Amendment 1; this spec includes the Custom hex addition that the
> brief lists as out-of-scope)

---

## Overview

Single page at `/settings`. Three sections:

1. **Appearance** — accent color picker (6 chips: Indigo, Teal, Burnt
   Orange, Monochrome, Cyan, Custom) + Custom hex input (visible only
   when Custom selected, per Amendment 1).
2. **Defaults** — Default Company (frappe-ui Autocomplete bound to
   `Cashew Settings.company`).
3. **Mappings** — two Desk deep-link rows (read-only in the SPA).

Dirty-state save bar at the bottom. Live preview on chip click before
save. Read-only mode when user lacks write perm on Cashew Settings.

---

## File tree

```
frontend/src/pages/
  Settings.vue                              # replaces c004 stub; mounts at "/settings"

frontend/src/components/settings/
  AppearanceSection.vue
  AccentColorPicker.vue                     # 6 chips + Custom hex input
  CustomHexInput.vue                        # validated 6-digit hex input
  DefaultsSection.vue
  MappingsSection.vue
  DeskLinkRow.vue
  SaveBar.vue                               # sticky-bottom dirty-state bar
  ReadOnlyBanner.vue                        # shown when can_write_settings === false
```

---

## State model

```js
const state = reactive({
  loading: true,
  saving: false,
  original: null,           // { accent_color, accent_color_custom, company } at load
  form: {                   // bound to inputs
    accent_color: 'Indigo',
    accent_color_custom: '',
    company: null,
  },
})

const canWrite = useHasWriteSettings()       // c004 boot accessor
const isDirty = computed(() => state.original
  && (state.form.accent_color !== state.original.accent_color
      || state.form.accent_color_custom !== state.original.accent_color_custom
      || state.form.company !== state.original.company))
```

Session-only (D6) for `state.form`. `state.original` is the read-back
from server on mount.

---

## Data flow

### Read on mount

```js
import { createResource } from 'frappe-ui'

const settingsRes = createResource({
  url: 'frappe.client.get_doc',
  cache: false,
  makeParams: () => ({ doctype: 'Cashew Settings', name: 'Cashew Settings' }),
  onSuccess: (data) => {
    state.original = {
      accent_color: data.accent_color || 'Indigo',
      accent_color_custom: data.accent_color_custom || '',
      company: data.company || null,
    }
    state.form = { ...state.original }
    state.loading = false
  },
  onError: () => { state.loading = false },
})
onMounted(() => settingsRes.reload())
```

D5 rule 1: read via frappe.client.get_doc. Cashew Settings is a
Single doctype; name === 'Cashew Settings'.

### Live preview (on chip click)

```js
function onAccentChange(preset) {
  state.form.accent_color = preset
  if (preset !== 'Custom') {
    applyAccentTheme({ accent_color: preset })   // c004 ThemeController, presets path
  } else if (state.form.accent_color_custom && isValidHex(state.form.accent_color_custom)) {
    applyAccentTheme({
      accent_color: 'Custom',
      accent_color_custom: state.form.accent_color_custom,
    })
  }
  // else: wait for valid hex before applying
}

function onCustomHexChange(hex) {
  state.form.accent_color_custom = hex
  if (state.form.accent_color === 'Custom' && isValidHex(hex)) {
    applyAccentTheme({ accent_color: 'Custom', accent_color_custom: hex })
  }
}
```

`applyAccentTheme(doc)` is c004's `applyThemeFromDoc(doc)` — writes the
4 CSS variables on `<html>`. Live preview is immediate; no debounce.

### Write on Save

```js
async function onSave() {
  state.saving = true
  try {
    // D5 rule 1 corollary: simple field writes via set_value are fine
    // for Cashew Settings. has_permission gate enforced server-side
    // (c010 audit confirms).
    await Promise.all([
      writeIfChanged('accent_color', state.form.accent_color),
      writeIfChanged('accent_color_custom', state.form.accent_color_custom),
      writeIfChanged('company', state.form.company),
    ])
    state.original = { ...state.form }
    toast('Settings saved')
    // c008 will push doc_update to all open tabs; this tab re-applies its
    // own change (idempotent).
  } catch (e) {
    // c004 interceptor already toasted
  } finally {
    state.saving = false
  }
}

function writeIfChanged(field, value) {
  if (state.form[field] === state.original[field]) return Promise.resolve()
  return frappeCall('frappe.client.set_value', {
    doctype: 'Cashew Settings',
    name: 'Cashew Settings',
    fieldname: field,
    value: value ?? '',
  })
}
```

`frappe.client.set_value` triggers `Cashew Settings.validate` on the
server (c013 spec's hook validates the custom hex regex). A bad hex
returns 417 ValidationError; c004's interceptor toasts; save bar
stays open.

### Discard

```js
function onDiscard() {
  // Revert live preview to original theme
  applyAccentTheme({
    accent_color: state.original.accent_color,
    accent_color_custom: state.original.accent_color_custom,
  })
  state.form = { ...state.original }
  toast('Discarded changes')
}
```

### Navigate-away guard

```js
import { onBeforeRouteLeave } from 'vue-router'

onBeforeRouteLeave((to, from, next) => {
  if (!isDirty.value) return next()
  // ConfirmDialog: "Leave with unsaved changes?"
  confirmDialog({
    title: 'Leave settings?',
    body: 'You have unsaved changes. Leaving will discard them.',
    confirmLabel: 'Leave',
    cancelLabel: 'Stay',
  }).then((ok) => {
    if (ok) {
      // Revert live preview when leaving
      applyAccentTheme({
        accent_color: state.original.accent_color,
        accent_color_custom: state.original.accent_color_custom,
      })
      next()
    } else {
      next(false)
    }
  })
})
```

---

## Components

### `Settings.vue` (page root)

```vue
<template>
  <div class="max-w-2xl mx-auto px-5 py-7 md:p-7">
    <PageHeader title="Settings" subtitle="App-wide configuration for Cashew." />

    <ReadOnlyBanner v-if="!canWrite" />

    <div class="space-y-6 mt-6">
      <AppearanceSection
        v-model:accent="state.form.accent_color"
        v-model:custom="state.form.accent_color_custom"
        :disabled="!canWrite"
        @preview="applyLivePreview"
      />
      <DefaultsSection v-model:company="state.form.company" :disabled="!canWrite" />
      <MappingsSection />
    </div>

    <SaveBar
      v-if="canWrite"
      :dirty="isDirty"
      :saving="state.saving"
      @save="onSave"
      @discard="onDiscard"
    />
  </div>
</template>
```

### `AppearanceSection.vue`

```vue
<template>
  <section>
    <h2 class="text-base font-medium">Appearance</h2>
    <p class="text-sm text-ink-3 mt-1">Choose the accent color used for buttons, links, charts and focus rings.</p>

    <div class="mt-4">
      <AccentColorPicker
        v-model="accent"
        :disabled="disabled"
        @change="onAccentChange"
      />
    </div>

    <CustomHexInput
      v-if="accent === 'Custom'"
      v-model="custom"
      :disabled="disabled"
      class="mt-4"
      @change="onCustomChange"
    />
  </section>
</template>
```

### `AccentColorPicker.vue`

```vue
<script setup>
const PRESETS = [
  { id: 'Indigo',       label: 'Indigo',       hex: '#4f46e5' },
  { id: 'Teal',         label: 'Teal',         hex: '#0d9488' },
  { id: 'Burnt Orange', label: 'Burnt Orange', hex: '#ea580c' },
  { id: 'Monochrome',   label: 'Monochrome',   hex: '#1f2937' },
  { id: 'Cyan',         label: 'Cyan',         hex: '#0891b2' },
  { id: 'Custom',       label: 'Custom',       hex: null },        // chip is a gradient ring; no flat swatch
]

const props = defineProps({ modelValue: String, disabled: Boolean })
const emit = defineEmits(['update:modelValue', 'change'])
</script>

<template>
  <div role="radiogroup" aria-label="Accent color" class="flex flex-wrap gap-3">
    <button
      v-for="p in PRESETS" :key="p.id"
      role="radio"
      :aria-checked="modelValue === p.id"
      :disabled="disabled"
      class="flex flex-col items-center gap-1.5"
      @click="$emit('update:modelValue', p.id); $emit('change', p.id)"
    >
      <div
        :class="[
          'w-9 h-9 rounded-md relative',
          modelValue === p.id ? 'ring-2 ring-offset-2 ring-accent' : 'hover:ring-2 hover:ring-offset-1 hover:ring-ink-3/40',
          disabled && 'opacity-50 cursor-not-allowed',
        ]"
        :style="p.hex ? `background-color: ${p.hex}` : 'background: conic-gradient(red, orange, yellow, green, blue, purple, red);'"
      >
        <Check v-if="modelValue === p.id" class="absolute -top-1 -right-1 w-3.5 h-3.5 bg-surface rounded-full p-0.5 text-accent" />
      </div>
      <span class="text-xs">{{ p.label }}</span>
    </button>
  </div>
</template>
```

The Custom chip uses a conic-gradient ring as its swatch (no flat
swatch — the chip says "pick your own").

### `CustomHexInput.vue`

```vue
<script setup>
const props = defineProps({ modelValue: String, disabled: Boolean })
const emit = defineEmits(['update:modelValue', 'change'])

const local = ref(props.modelValue || '')
const error = ref(null)
const HEX_RE = /^#[0-9a-fA-F]{6}$/

function onInput(value) {
  let v = value
  if (v && !v.startsWith('#')) v = '#' + v
  local.value = v
  if (!v) { error.value = null; emit('update:modelValue', ''); return }
  if (HEX_RE.test(v)) {
    error.value = null
    emit('update:modelValue', v)
    emit('change', v)
  } else {
    error.value = 'Must be 6-digit hex (e.g. #4f46e5)'
  }
}

watch(() => props.modelValue, (v) => { local.value = v || '' })
</script>

<template>
  <div>
    <label class="block text-sm font-medium">Custom hex color</label>
    <p class="text-xs text-ink-3 mt-0.5">Enter a 6-digit hex (e.g. #4f46e5). Shell will derive lighter/darker shades.</p>
    <div class="flex items-center gap-2 mt-2">
      <input
        type="text"
        :value="local"
        :disabled="disabled"
        placeholder="#4f46e5"
        maxlength="7"
        class="border border-border rounded px-2 py-1 text-sm font-mono w-32"
        @input="e => onInput(e.target.value)"
      />
      <div v-if="local && !error" class="w-6 h-6 rounded border border-border" :style="`background-color: ${local}`" />
    </div>
    <p v-if="error" class="text-xs text-danger mt-1">{{ error }}</p>
  </div>
</template>
```

Validation: client-side regex matches the server-side validator
(c013's hook). Empty value allowed (means "not set yet"); on Save the
server's validator throws if `accent_color === 'Custom'` and
`accent_color_custom` is empty / invalid.

### `DefaultsSection.vue`

```vue
<template>
  <section>
    <h2 class="text-base font-medium">Defaults</h2>
    <p class="text-sm text-ink-3 mt-1">Default values that pre-fill when starting a new import.</p>
    <div class="mt-4 max-w-md">
      <label class="block text-sm font-medium">Default Company</label>
      <Autocomplete
        v-model="company"
        reference_doctype="Cashew Settings"
        reference_fieldname="company"
        :disabled="disabled"
        class="mt-1"
      />
      <p class="text-xs text-ink-3 mt-1">Pre-selected when creating a new import from /runs/new.</p>
    </div>
  </section>
</template>
```

D5 rule 2: `reference_doctype="Cashew Settings"` +
`reference_fieldname="company"` so any `set_query` on
`Cashew Settings.company` honors.

### `MappingsSection.vue`

```vue
<template>
  <section>
    <h2 class="text-base font-medium">Mappings</h2>
    <p class="text-sm text-ink-3 mt-1">Mapping tables are managed in the Desk form for now.</p>
    <div class="mt-4 space-y-2">
      <DeskLinkRow
        title="Cashew Category Mapping"
        subtitle="Map Cashew categories to Frappe Accounts."
        href="/app/cashew-category-mapping"
      />
      <DeskLinkRow
        title="Cashew Account Mapping"
        subtitle="Map Cashew accounts to Frappe Accounts."
        href="/app/cashew-account-mapping"
      />
    </div>
  </section>
</template>
```

`DeskLinkRow.vue`: subdued background card; left = title + subtitle;
right = `<a href="...">Manage on Desk →</a>` (same tab — user
returns via Back-to-Desk app-switcher in c004 shell).

### `SaveBar.vue`

```vue
<template>
  <Transition name="slide-up">
    <div v-if="dirty" class="fixed left-0 right-0 bottom-0 md:bottom-0 px-4 py-3 bg-surface border-t border-border z-30">
      <div class="max-w-2xl mx-auto flex items-center justify-between gap-3">
        <span class="text-sm text-ink-3">Unsaved changes.</span>
        <div class="flex gap-2">
          <Button variant="ghost" :disabled="saving" @click="$emit('discard')">Discard</Button>
          <Button variant="solid" theme="accent" :loading="saving" @click="$emit('save')">Save changes</Button>
        </div>
      </div>
    </div>
  </Transition>
</template>
```

On mobile, the bar sits above the c004 MobileBottomNav — adjust
positioning so they stack: `bottom-16` on `<md`, `bottom-0` on `>=md`.
Bottom-nav has `z-40`; SaveBar `z-30` underneath so it tucks above
the nav rather than overlapping content.

### `ReadOnlyBanner.vue`

Subdued amber banner:
> Read-only — ask a System Manager to change Settings.

Renders when `boot.can_write_settings === false`. All inputs
under `Settings.vue` set `:disabled="true"`. SaveBar hidden.

---

## Acceptance

- [ ] `/settings` renders at the third sidebar nav item.
- [ ] Skeleton state on first fetch.
- [ ] Six accent chips render: Indigo, Teal, Burnt Orange, Monochrome,
      Cyan, Custom. Indigo is initially selected when no value set.
- [ ] Selecting a preset (non-Custom) immediately re-paints the SPA
      accent (live preview).
- [ ] Selecting Custom reveals the hex input below the chip row.
- [ ] Typing an invalid hex shows a validation error message; valid hex
      live-paints the accent.
- [ ] Form dirty-state turns on when any field differs from original;
      SaveBar slides in.
- [ ] Save calls `frappe.client.set_value` for each changed field;
      success toast `Settings saved`; SaveBar slides away.
- [ ] Server validation error (e.g. bad hex) keeps SaveBar open;
      error toast surfaces.
- [ ] Discard reverts form to `state.original` AND reverts the live
      preview to original theme.
- [ ] Navigate-away with dirty state shows ConfirmDialog; choosing
      Leave reverts live preview before navigating.
- [ ] Default Company Autocomplete renders + honors any `set_query`
      registered for Cashew Settings.company.
- [ ] Mappings section renders two same-tab Desk deep-links.
- [ ] When user lacks Cashew Settings write perm
      (`boot.can_write_settings === false`):
      - ReadOnlyBanner shows
      - All inputs disabled
      - SaveBar hidden
- [ ] When another tab saves a new accent color, this tab re-paints
      within ~1s without reload (c008 handles propagation; no extra
      code here).
- [ ] No `localStorage` / `sessionStorage` writes — grep zero.

---

## Files touched

```
frontend/src/pages/Settings.vue                                # REPLACE c004 stub
frontend/src/components/settings/AppearanceSection.vue         # NEW
frontend/src/components/settings/AccentColorPicker.vue         # NEW
frontend/src/components/settings/CustomHexInput.vue            # NEW
frontend/src/components/settings/DefaultsSection.vue           # NEW
frontend/src/components/settings/MappingsSection.vue           # NEW
frontend/src/components/settings/DeskLinkRow.vue               # NEW
frontend/src/components/settings/SaveBar.vue                   # NEW
frontend/src/components/settings/ReadOnlyBanner.vue            # NEW
```

No new boot fields. No new whitelisted methods. No new Python.

`Cashew Settings.accent_color` + `accent_color_custom` already added
by c013. The server-side validator hook is also c013's responsibility.

---

## TD calls inside arch envelope (not surfacing)

- **6 chips (including Custom)** — Amendment 1 brought Custom into
  scope; brief's "out of scope: custom hex picker" is superseded. Spec
  reflects current state.
- **Custom chip swatch as conic-gradient ring.** No flat color — the
  swatch's visual says "pick your own". Hex input below the chips
  drives the actual color.
- **Save via `frappe.client.set_value` per field**, not one batch.
  Three small parallel calls; same network cost; cleaner error
  handling (one bad field doesn't reject the others — but in practice
  the validator runs on doc.save, not per set_value; we accept the
  per-field path because Cashew Settings is Single and the validator
  is cheap).
- **Navigate-away guard via `onBeforeRouteLeave`.** No `beforeunload`
  guard — tab-close is the user's choice; we don't fight it.
- **Live-preview state lives on `<html>` CSS vars** (via c004's
  ThemeController), not in `state.form`. Discarding reverts the vars
  in addition to the form.
- **Sample chip hex values locked here too** — they MUST match
  c004's PRESET_TABLE byte-for-byte. If c004's table changes, this
  list changes. (Constants colocated in two places; cost is low
  and the picker SFC needs the values for the swatch render. If
  drift becomes a worry, move PRESET_TABLE to a shared module
  imported by both.)

---

## Open items (handed off)

- **Color-blind / contrast checks for the 5 preset accents.** None of
  the presets are inherently inaccessible against the default surface
  palette, but verify with a contrast tool before final design sign-off.
- **Eye-dropper UI for Custom.** Browser's `<input type="color">`
  would give a native picker — considered but rejected because (a)
  it forces a popup; (b) it doesn't show the hex value alongside; (c)
  the typed-hex path is sufficient for v1. Could ship a `<input
  type="color">` alongside the text input in a future iteration.
- **Shade preview.** Show the derived `-700` / `-100` / `-50` shades
  next to the chosen accent so the user can preview what charts /
  hover states will look like. Deferred.
- **`reference_fieldname="company"` for Default Company** — verify
  fieldname matches `Cashew Settings.json`. If a `set_query` is
  registered (e.g. filter `disabled=0`), Autocomplete honors it
  automatically.
- **Save action audit** — c010 audit confirms that `set_value` on
  Cashew Settings checks write perm; if not, c010 adds the
  `has_permission` gate.
