<script setup>
import { useSession } from '@/boot';
import { Avatar, Dropdown } from 'frappe-ui';
import { ChevronUp } from 'lucide-vue-next';

const session = useSession();

function logout() {
  window.location.href = '/api/method/logout';
}
function openProfile() {
  window.open(`/app/user/${encodeURIComponent(session.user)}`, '_blank', 'noopener');
}
function backToDesk() {
  window.location.href = '/app';
}

const options = [
  { label: 'Open profile', onClick: openProfile },
  { label: 'Back to Desk', onClick: backToDesk },
  { label: 'Log out', onClick: logout },
];
</script>

<template>
  <Dropdown placement="top-start" :options="options">
    <template #default="{ open }">
      <button
        type="button"
        class="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-gray-50 text-left"
        :aria-expanded="open"
      >
        <Avatar :label="session.fullName" :image="session.image" size="sm" />
        <span class="flex-1 min-w-0">
          <span class="block text-sm font-medium leading-tight truncate">{{ session.fullName }}</span>
          <span class="block text-[11px] text-gray-500 leading-tight truncate">{{ session.user }}</span>
        </span>
        <ChevronUp :size="14" class="text-gray-400" />
      </button>
    </template>
  </Dropdown>
</template>
