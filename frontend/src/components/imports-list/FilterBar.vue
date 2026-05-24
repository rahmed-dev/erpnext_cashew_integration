<script setup>
import { ref } from 'vue';
import StatusFilter from './StatusFilter.vue';
import PeriodFilter from './PeriodFilter.vue';
import CompanyFilter from './CompanyFilter.vue';
import { useIsMobile } from '@/state/useIsMobile';
import { Input, Button, Dialog } from 'frappe-ui';
import { Search, Filter as FilterIcon, X } from 'lucide-vue-next';

const props = defineProps({ filters: { type: Object, required: true } });
const emit = defineEmits(['update:filters', 'clear']);

const isMobile = useIsMobile();
const sheetOpen = ref(false);
const companyVisible = ref(false);

function patch(partial) {
  emit('update:filters', { ...props.filters, ...partial });
}
function setStatus(v) { patch({ status: v }); }
function setPeriod(v) { patch({ period: v }); }
function setPeriodRange(v) { patch({ period_range: v }); }
function setCompany(v) { patch({ company: v }); }
function setSearch(e) { patch({ search: typeof e === 'string' ? e : e.target.value }); }

function hasAny() {
  return Boolean(
    props.filters.status?.length ||
    props.filters.period !== 'any' ||
    props.filters.company ||
    props.filters.search,
  );
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-2 mb-4">
    <!-- Desktop search input -->
    <div class="relative flex-1 min-w-[180px] max-w-md hidden md:block">
      <Search :size="14" class="absolute left-2.5 top-2.5 text-gray-400" />
      <Input
        :modelValue="filters.search"
        placeholder="Search by run name…"
        class="pl-8"
        @update:modelValue="(v) => setSearch(v)"
      />
    </div>

    <!-- Desktop filter chips -->
    <div class="hidden md:flex items-center gap-2 flex-wrap">
      <StatusFilter :modelValue="filters.status" @update:modelValue="setStatus" />
      <PeriodFilter
        :modelValue="filters.period"
        :range="filters.period_range"
        @update:modelValue="setPeriod"
        @update:range="setPeriodRange"
      />
      <CompanyFilter
        :modelValue="filters.company"
        @update:modelValue="setCompany"
        @visible="(v) => (companyVisible = v)"
      />
      <button
        v-if="hasAny()"
        type="button"
        class="text-xs text-gray-500 hover:text-cs-accent-700 inline-flex items-center gap-1"
        @click="$emit('clear')"
      >
        <X :size="12" /> Clear filters
      </button>
    </div>

    <!-- Mobile compact: search + Filters button -->
    <div class="flex md:hidden w-full items-center gap-2">
      <div class="relative flex-1">
        <Search :size="14" class="absolute left-2.5 top-2.5 text-gray-400" />
        <Input
          :modelValue="filters.search"
          placeholder="Search…"
          class="pl-8"
          @update:modelValue="(v) => setSearch(v)"
        />
      </div>
      <Button variant="outline" @click="sheetOpen = true">
        <template #prefix><FilterIcon :size="14" /></template>
        Filters
      </Button>
    </div>

    <!-- Mobile bottom-sheet style dialog -->
    <Dialog v-model="sheetOpen">
      <template #body>
        <div class="p-5 space-y-3">
          <h3 class="text-base font-semibold">Filters</h3>
          <div class="space-y-2">
            <div>
              <p class="text-[11px] uppercase tracking-wider text-gray-500 mb-1">Status</p>
              <StatusFilter :modelValue="filters.status" @update:modelValue="setStatus" />
            </div>
            <div>
              <p class="text-[11px] uppercase tracking-wider text-gray-500 mb-1">Period</p>
              <PeriodFilter
                :modelValue="filters.period"
                :range="filters.period_range"
                @update:modelValue="setPeriod"
                @update:range="setPeriodRange"
              />
            </div>
            <div v-if="companyVisible">
              <p class="text-[11px] uppercase tracking-wider text-gray-500 mb-1">Company</p>
              <CompanyFilter
                :modelValue="filters.company"
                @update:modelValue="setCompany"
                @visible="(v) => (companyVisible = v)"
              />
            </div>
          </div>
          <div class="flex justify-between items-center pt-3 border-t border-gray-100">
            <button class="text-xs text-gray-500 hover:underline" @click="$emit('clear')">
              Clear all
            </button>
            <Button variant="solid" theme="accent" @click="sheetOpen = false">Done</Button>
          </div>
        </div>
      </template>
    </Dialog>
  </div>
</template>
