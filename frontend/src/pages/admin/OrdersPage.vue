<script setup lang="ts">
import { ORDER_STATUS_TAG } from "@/constants/referenceData";
import { onMounted, reactive, ref } from "vue";

import EditorIcon from "@/components/EditorIcon.vue";
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

const showForm = ref(false);

async function submit() {
  formError.value = "";
  try {
    await store.createOrder(form);
    form.customer_name = "";
    form.customer_email = "";
    form.notes = "";
    form.lines = [];
    showForm.value = false;
  } catch (err) {
    formError.value = err instanceof ApiError ? err.message : t("common.error");
  }
}

const statusColor: Record<OrderStatus, string> = ORDER_STATUS_TAG;
</script>

<template>
  <div class="page max-w-4xl">
    <header class="page-head">
      <div>
        <h1 class="page-title">{{ t("orders.title") }}</h1>
        <p class="page-lead">{{ t("orders.lead") }}</p>
      </div>
      <button v-if="!showForm" class="btn btn-primary" @click="showForm = true">+ {{ t("orders.addTitle") }}</button>
    </header>

    <div v-if="showForm" class="sheet p-5 mb-8">
      <h2 class="sheet-title mb-4">{{ t("orders.addTitle") }}</h2>
      <form class="space-y-3" @submit.prevent="submit">
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="field-label">{{ t("orders.customerName") }}</span>
            <input v-model="form.customer_name" required autocomplete="name" class="input w-full" />
          </label>
          <label class="block"><span class="field-label">{{ t("orders.customerEmail") }}</span>
            <input v-model="form.customer_email" type="email" autocomplete="email" class="input w-full" />
          </label>
          <label class="block col-span-2"><span class="field-label">{{ t("common.notes") }}</span>
            <textarea v-model="form.notes" class="input w-full" rows="2"></textarea>
          </label>
        </div>
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-slate-700">{{ t("orders.lines") }}</span>
            <button type="button" class="link-action" @click="addLine">{{ t("orders.addLine") }}</button>
          </div>
          <div v-for="(line, i) in form.lines" :key="i" class="grid grid-cols-12 gap-2 mb-2 items-center">
            <select v-model.number="line.knife_model_id" :aria-label="t('orders.model')" class="col-span-8 input-sm">
              <option v-for="km in store.knifeModels" :key="km.id" :value="km.id">{{ km.name }}</option>
            </select>
            <input v-model.number="line.quantity" type="number" min="1" :aria-label="t('orders.quantity')" class="col-span-3 input-sm" />
            <button type="button" class="col-span-1 justify-self-center p-1 rounded text-slate-500 hover:text-red-700 hover:bg-slate-100" :aria-label="t('common.delete')" @click="removeLine(i)"><EditorIcon name="close" :size="14" /></button>
          </div>
        </div>
        <p v-if="formError" role="alert" class="text-sm text-red-700">{{ formError }}</p>
        <div class="flex gap-2">
          <button type="submit" class="btn btn-primary">{{ t("orders.createOrder") }}</button>
          <button type="button" class="btn btn-outline" @click="showForm = false">{{ t("common.cancel") }}</button>
        </div>
      </form>
    </div>

    <div class="space-y-3">
      <p v-if="!store.orders.length" class="sheet p-6 text-sm text-slate-600">{{ t("orders.empty") }}</p>
      <router-link v-for="o in store.orders" :key="o.id" :to="`/orders/${o.id}`" class="block sheet p-4 transition-colors hover:border-slate-300 hover:bg-white">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-semibold text-slate-900">{{ o.customer_name }}</span>
            <span class="text-xs text-slate-500 tabular-nums">#{{ o.id }}</span>
            <span v-if="o.is_mock" class="tag tag-neutral">{{ t("common.demo") }}</span>
          </div>
          <span class="tag font-medium" :class="statusColor[o.status]">{{ t(`orders.status.${o.status}`) }}</span>
        </div>
        <p class="text-sm text-slate-500 mt-1">{{ o.lines.map((l) => `${l.quantity} × ${l.knife_model_name}`).join(", ") || t("orders.noLines") }}</p>
      </router-link>
    </div>
  </div>
</template>
