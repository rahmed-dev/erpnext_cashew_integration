<script setup>
import { ref, computed } from 'vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import SkeletonBlock from '@/components/shared/SkeletonBlock.vue';
import DeltaChip from '@/components/shared/DeltaChip.vue';
import { ChevronRight } from 'lucide-vue-next';

const props = defineProps({
  tileId: { type: String, default: '' },
  label: { type: String, required: true },
  icon: { type: Object, default: null },
  amount: { type: [Number, null], default: null },
  prior: { type: [Number, null], default: null },
  currency: { type: String, default: 'PKR' },
  loading: { type: Boolean, default: false },
  invert: { type: Boolean, default: false },
  clickable: { type: Boolean, default: false },
  breakdown: { type: [Object, null], default: null },
  // f012 c003 — a short line under the figure ("12 invoices"). The KPI tiles
  // carry a volume alongside their value, and a second tile for the count would
  // be a parallel card system for one number.
  caption: { type: String, default: '' },
});
const emit = defineEmits(['click']);

// Floating breakdown panel — same pattern as IncomeExpenseChart's slice tooltip.
// Pinned to viewport via fixed positioning so it can escape the tile bounds.
const hovering = ref(false);
const cursor = ref({ x: 0, y: 0 });

function onEnter(e) {
  hovering.value = true;
  cursor.value = { x: e.clientX, y: e.clientY };
}
function onMove(e) {
  if (hovering.value) cursor.value = { x: e.clientX, y: e.clientY };
}
function onLeave() {
  hovering.value = false;
}
function onClick() {
  if (!props.clickable || props.loading) return;
  hovering.value = false;
  emit('click');
}

const isPartyTile = computed(() => props.tileId === 'receivable' || props.tileId === 'payable');
const companyCurrency = computed(() => props.breakdown?.company_currency || '');
const items = computed(() => props.breakdown?.items || []);

const rowsToShow = computed(() => {
  const top = items.value.slice(0, 5);
  const tail = items.value.slice(5);
  if (tail.length) {
    const sum = tail.reduce((s, x) => s + Math.abs(x.balance || 0), 0);
    top.push({ _tail: true, _label: `+ ${tail.length} more`, balance: sum, currency: companyCurrency.value });
  }
  return top;
});

const showPanel = computed(
  () => hovering.value && props.clickable && !props.loading && items.value.length > 0,
);

const tooltipStyle = computed(() => {
  if (typeof window === 'undefined') return {};
  const PAD = 12;
  const W = 280;
  const H = 280; // estimate; clamp keeps it inside viewport
  let left = cursor.value.x + PAD;
  if (left + W > window.innerWidth - 4) left = Math.max(4, cursor.value.x - W - PAD);
  let top = cursor.value.y + PAD;
  if (top + H > window.innerHeight - 4) top = Math.max(4, cursor.value.y - H - PAD);
  return {
    position: 'fixed',
    left: `${left}px`,
    top: `${top}px`,
    width: `${W}px`,
    zIndex: 50,
  };
});

function isForeign(it) {
  return !!(companyCurrency.value && it.currency && companyCurrency.value !== it.currency);
}
function nameOf(it) {
  if (it._tail) return it._label;
  return isPartyTile.value ? it.party : it.account;
}
function subOf(it) {
  if (it._tail) return null;
  return isPartyTile.value ? it.party_type : it.account_type;
}
</script>

<template>
  <component
    :is="clickable ? 'button' : 'div'"
    :type="clickable ? 'button' : undefined"
    :class="[
      'rounded-lg border border-gray-200 bg-white p-3 text-left w-full block',
      clickable && !loading
        ? 'cursor-pointer hover:border-[var(--cs-accent)] hover:shadow-sm transition'
        : '',
    ]"
    @mouseenter="onEnter"
    @mousemove="onMove"
    @mouseleave="onLeave"
    @click="onClick"
  >
    <!-- Icon, label, delta and chevron share ONE line. Each on its own row cost
         a full line of height per tile, and with seven tiles that was most of
         the first screen spent on chrome rather than figures — worst on a phone,
         where the tiles stack two-up and the rows multiply. -->
    <div class="flex items-center gap-1.5 min-w-0">
      <span class="shrink-0 inline-flex items-center justify-center w-5 h-5 rounded bg-[var(--cs-accent-50)] text-[var(--cs-accent)]">
        <component :is="icon" :size="12" />
      </span>
      <span class="text-[11px] text-gray-500 uppercase tracking-wide truncate min-w-0">{{ label }}</span>
      <span class="ml-auto shrink-0 flex items-center gap-1">
        <DeltaChip v-if="!loading && prior != null" :current="amount" :prior="prior" :invert="invert" />
        <ChevronRight v-if="clickable && !loading" :size="14" class="text-gray-400" />
      </span>
    </div>
    <SkeletonBlock v-if="loading" class="h-6 mt-1.5 w-2/3" />
    <div v-else class="mt-1">
      <AmountDisplay :amount="amount" :currency="currency" big />
      <!-- The caption is the tile's only optional row, so it carries no top
           margin of its own — a tile without one must not reserve the space. -->
      <div v-if="caption" class="text-[11px] text-gray-500">{{ caption }}</div>
    </div>

    <Teleport to="body">
      <div
        v-if="showPanel"
        class="rounded-lg border border-gray-200 bg-white shadow-lg p-3 pointer-events-none"
        :style="tooltipStyle"
      >
        <div class="flex items-center justify-between gap-3 mb-2 pb-2 border-b border-gray-100">
          <span class="text-[11px] font-semibold uppercase tracking-wide text-gray-700">{{ label }}</span>
          <span class="text-xs font-semibold tabular-nums text-gray-900">
            <AmountDisplay :amount="amount" :currency="currency" />
          </span>
        </div>
        <div class="text-[10px] uppercase tracking-wide text-gray-400 mb-1">
          {{ isPartyTile ? 'Top parties' : 'Top accounts' }}
        </div>
        <ul class="space-y-1.5">
          <li
            v-for="(it, i) in rowsToShow"
            :key="i"
            class="flex items-start justify-between gap-2 text-xs"
          >
            <div class="min-w-0 flex-1">
              <div :class="['truncate', it._tail ? 'text-gray-500 italic' : 'text-gray-700']">
                {{ nameOf(it) }}
              </div>
              <div v-if="subOf(it)" class="text-[10px] text-gray-400 truncate">{{ subOf(it) }}</div>
            </div>
            <div class="shrink-0 text-right tabular-nums">
              <AmountDisplay :amount="it.balance" :currency="it.currency" class="text-gray-900" />
              <div
                v-if="isForeign(it) && it.base_balance != null"
                class="text-[9px] text-gray-400"
              >
                ≈ <AmountDisplay :amount="it.base_balance" :currency="it.base_currency || companyCurrency" />
              </div>
            </div>
          </li>
        </ul>
      </div>
    </Teleport>
  </component>
</template>
