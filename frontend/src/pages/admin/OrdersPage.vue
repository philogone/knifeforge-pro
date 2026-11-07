<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { OrderLine, OrderStatus } from "@/types";

const { t } = useI18n();
const store = useAppStore();
onMounted(() => {
  store.fetchOrders();
  store.fetchKnifeModels();
});

const form = reactive({
  customer_name: "",
  customer_email: "",
  notes: "",
  lines: [] as OrderLine[],
});
const formError = ref("");

function addLine() {
  form.lines.push({ knife_model_id: store.knifeModels[0]?.id ?? 0, quantity: 1 });
}
function removeLine(i: number) {
  form.lines.splice(i, 1);
}

async function submit() {
  formError.value = "";
  try {
    await store.createOrder(form);
    form.customer_name = "";
    form.customer_email = "";
    form.notes = "";
    form.lines = [];
  } catch (err) {
    formError.value = err instanceof ApiError ? err.message : t("common.error");
  }
}

const statusColor: Record<OrderStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  confirmed: "bg-blue-50 text-blue-700",
  completed: "bg-green-50 text-green-700",
  cancelled: "bg-red-50 text-red-700",
};
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-6">{{ t("orders.title") }}</h1>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-8">
      <h2 class="font-semibold text-slate-900 mb-3">{{ t("orders.addTitle") }}</h2>
      <form class="space-y-3" @submit.prevent="submit">
        <div class="grid grid-cols-2 gap-3">
          <input v-model="form.customer_name" :placeholder="t('orders.customerName')" required class="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input v-model="form.customer_email" type="email" :placeholder="t('orders.customerEmail')" class="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <textarea v-model="form.notes" :placeholder="t('common.notes')" class="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm" rows="2"></textarea>
        </div>
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-slate-700">{{ t("orders.lines") }}</span>
            <button type="button" class="text-sm text-accent-600" @click="addLine">{{ t("orders.addLine") }}</button>
          </div>
          <div v-for="(line, i) in form.lines" :key="i" class="grid grid-cols-12 gap-2 mb-2 items-center">
            <select v-model.number="line.knife_model_id" class="col-span-8 rounded-lg border border-slate-300 px-2 py-1 text-sm">
              <option v-for="km in store.knifeModels" :key="km.id" :value="km.id">{{ km.name }}</option>
            </select>
            <input v-model.number="line.quantity" type="number" min="1" class="col-span-3 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <button type="button" class="col-span-1 text-red-600 text-sm" @click="removeLine(i)">✕</button>
          </div>
        </div>
        <p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>
        <button type="submit" class="bg-accent-600 hover:bg-accent-700 text-white text-sm font-medium rounded-lg px-4 py-2">{{ t("orders.createOrder") }}</button>
      </form>
    </div>

    <div class="space-y-3">
      <router-link v-for="o in store.orders" :key="o.id" :to="`/orders/${o.id}`" class="block bg-white rounded-xl border border-slate-200 p-4 hover:border-accent-300">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-medium text-slate-900">{{ o.customer_name }}</span>
            <span v-if="o.is_mock" class="ml-2 text-xs text-slate-500 bg-slate-100 rounded px-1.5 py-0.5">{{ t("common.demo") }}</span>
          </div>
          <span class="text-xs font-medium rounded px-2 py-1" :class="statusColor[o.status]">{{ t(`orders.status.${o.status}`) }}</span>
        </div>
        <p class="text-sm text-slate-500 mt-1">{{ o.lines.map((l) => `${l.quantity}x ${l.knife_model_name}`).join(", ") || t("orders.noLines") }}</p>
      </router-link>
    </div>
  </div>
</template>
