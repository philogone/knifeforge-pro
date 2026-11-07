<script setup lang="ts">
import { onMounted, ref } from "vue";

import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { ProductionOverview } from "@/types";

const { t, qty } = useI18n();
const store = useAppStore();
const overview = ref<ProductionOverview | null>(null);

onMounted(async () => {
  overview.value = await store.fetchProductionOverview();
});
</script>

<template>
  <div v-if="overview" class="page max-w-4xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("production.title") }}</h1>
        <p class="page-lead">{{ t("production.subtitle") }}</p>
      </div>
    </header>

    <div class="sheet p-4 mb-6">
      <h2 class="sheet-title mb-3">{{ t("production.demandTitle") }}</h2>
      <div v-if="overview.materials.length === 0" class="text-sm text-slate-500">{{ t("production.noDrafts") }}</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500">
            <th class="font-normal pb-1">{{ t("production.material") }}</th>
            <th class="font-normal pb-1">{{ t("production.demand") }}</th>
            <th class="font-normal pb-1">{{ t("production.available") }}</th>
            <th class="font-normal pb-1">{{ t("production.shortfall") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in overview.materials" :key="m.material_id" class="border-t border-slate-100">
            <td class="py-1.5">{{ m.material_name }}</td>
            <td class="py-1.5">{{ qty(m.demand, m.unit) }}</td>
            <td class="py-1.5">{{ qty(m.available, m.unit) }}</td>
            <td class="py-1.5">
              <span v-if="m.shortfall > 0" class="tag tag-danger font-medium">− {{ qty(m.shortfall, m.unit) }}</span>
              <span v-else class="tag tag-success">✓ {{ t("orderDetail.ok") }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="sheet p-4">
      <h2 class="sheet-title mb-3">{{ t("production.ordersTitle") }}</h2>
      <div v-if="overview.orders.length === 0" class="text-sm text-slate-500">{{ t("production.noDrafts") }}</div>
      <div v-else class="space-y-2">
        <router-link
          v-for="o in overview.orders"
          :key="o.order_id"
          :to="`/orders/${o.order_id}`"
          class="flex items-center justify-between border-t border-slate-100 first:border-0 pt-2 first:pt-0 hover:bg-slate-50 -mx-2 px-2 rounded"
        >
          <div>
            <span class="text-sm font-medium text-slate-800">{{ o.customer_name }}</span>
            <span class="text-sm text-slate-500 ml-2">{{ o.lines.join(", ") }}</span>
          </div>
          <span class="text-xs font-medium rounded px-2 py-1" :class="o.feasible ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">
            {{ o.feasible ? t("production.feasible") : t("production.short") }}
          </span>
        </router-link>
      </div>
    </div>
  </div>
</template>
