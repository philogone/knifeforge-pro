<script setup lang="ts">
/** Search box + sort select shown above a list; the page owns the state (v-model). */
import { useI18n } from "@/i18n";

defineProps<{ placeholder: string; sorts: { key: string; label: string }[]; shown: number; total: number }>();
const query = defineModel<string>("query", { required: true });
const sortKey = defineModel<string>("sort", { required: true });
const { t } = useI18n();
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <label class="relative flex-1 min-w-[14rem] max-w-md">
      <span class="sr-only">{{ placeholder }}</span>
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
        <circle cx="8.5" cy="8.5" r="5.5" /><path d="M13 13l4 4" />
      </svg>
      <input v-model="query" type="search" :placeholder="placeholder" class="input w-full pl-9" @keydown.esc="query = ''" />
    </label>
    <label class="flex items-center gap-2 text-sm text-slate-600">
      {{ t("list.sortBy") }}
      <select v-model="sortKey" class="input-sm">
        <option v-for="s in sorts" :key="s.key" :value="s.key">{{ s.label }}</option>
      </select>
    </label>
    <slot />
    <p class="ml-auto text-xs text-slate-500 tabular-nums" aria-live="polite">
      {{ shown === total ? t("list.count", { n: total }) : t("list.countFiltered", { shown, total }) }}
    </p>
  </div>
</template>
