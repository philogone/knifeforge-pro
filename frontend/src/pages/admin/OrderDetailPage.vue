<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/composables/useApi";
import { DOCUMENT_STATUS_TAG, ORDER_STAGES, ORDER_STATUS_TAG } from "@/constants/referenceData";
import { useI18n } from "@/i18n";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";
import type { Customer, FeasibilityResult, Order, SalesDocument } from "@/types";

const { t, qty, money } = useI18n();
const customers = ref<Customer[]>([]);
const documents = ref<SalesDocument[]>([]);

async function loadExtras() {
  if (!order.value) return;
  [customers.value, documents.value] = await Promise.all([
    store.fetchCustomers().then((cs) => cs.filter((c) => !c.anonymized_at || c.id === order.value?.customer_id)),
    store.fetchDocuments({ order_id: order.value.id }),
  ]);
}

async function patch(payload: Record<string, unknown>) {
  if (!order.value) return;
  order.value = await store.updateOrder(order.value.id, payload);
}

async function newDocument(kind: "quote" | "invoice") {
  if (!order.value) return;
  const doc = await store.documentFromOrder(order.value.id, kind);
  router.push(`/documents/${doc.id}`);
}
const route = useRoute();
const router = useRouter();
const store = useAppStore();

const orderId = Number(route.params.id);
const order = ref<Order | null>(null);
const feasibility = ref<FeasibilityResult | null>(null);
const actionError = ref("");
const loading = ref(false);

async function load() {
  order.value = await store.fetchOrder(orderId);
  if (order.value.status === "draft" && order.value.lines.length > 0) {
    feasibility.value = await store.checkFeasibility(orderId);
  } else {
    feasibility.value = null;
  }
}

onMounted(async () => {
  await load();
  await loadExtras();
});

async function runAction(action: "confirm" | "cancel" | "complete") {
  actionError.value = "";
  loading.value = true;
  try {
    if (action === "confirm") await store.confirmOrder(orderId);
    if (action === "cancel") await store.cancelOrder(orderId);
    if (action === "complete") await store.completeOrder(orderId);
    await load();
  } catch (err) {
    if (err instanceof ApiError) {
      const detail = err.detail as { message?: string; feasibility?: FeasibilityResult } | string;
      if (typeof detail === "object" && detail.feasibility) {
        feasibility.value = detail.feasibility;
        actionError.value = t("orderDetail.insufficientStock");
      } else {
        actionError.value = errorMessage(err, t);
      }
    } else {
      actionError.value = errorMessage(err, t);
    }
  } finally {
    loading.value = false;
  }
}

async function remove() {
  if (!order.value) return;
  if (!confirm(t("common.confirmDeleteNamed", { name: order.value.customer_name }))) return;
  await store.deleteOrder(order.value.id);
  router.push("/orders");
}
</script>

<template>
  <div v-if="order" class="page max-w-6xl">
    <router-link to="/orders" class="back-link">&larr; {{ t("common.backToList") }}</router-link>
    <div class="flex items-center gap-3">
      <h1 class="page-title">{{ order.customer_name }}</h1>
      <span class="tag font-medium" :class="ORDER_STATUS_TAG[order.status]">{{ t(`orders.status.${order.status}`) }}</span>
    </div>
    <p v-if="order.customer_email" class="text-sm text-slate-500 mt-1">{{ order.customer_email }}</p>

    <section class="sheet p-4 mt-6">
      <div class="field-grid grid sm:grid-cols-3 gap-3">
        <div>
          <label class="field-label" for="od-customer">{{ t("doc.customer") }}</label>
          <select id="od-customer" :value="order.customer_id ?? ''" class="input w-full" @change="patch({ customer_id: Number(($event.target as HTMLSelectElement).value) || null })">
            <option value="">{{ t("orderDetail.noCustomer") }}</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.is_business && c.company_name ? c.company_name : c.name }}</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="od-due">{{ t("orderDetail.dueDate") }}</label>
          <input id="od-due" type="date" :value="order.due_date ?? ''" class="input w-full" @change="patch({ due_date: ($event.target as HTMLInputElement).value || null })" />
        </div>
        <div>
          <label class="field-label" for="od-stage">{{ t("orderDetail.stage") }}</label>
          <select id="od-stage" :value="order.stage" class="input w-full" @change="patch({ stage: ($event.target as HTMLSelectElement).value })">
            <option v-for="s in ORDER_STAGES" :key="s" :value="s">{{ t(`orders.stage.${s}`) }}</option>
          </select>
        </div>
      </div>
      <ol class="mt-4 flex items-center gap-1" :aria-label="t('orderDetail.stage')">
        <li v-for="(s, i) in ORDER_STAGES" :key="s" class="flex-1">
          <div class="h-1.5 rounded-full" :class="i <= ORDER_STAGES.indexOf(order.stage) ? 'bg-accent-600' : 'bg-slate-200'"></div>
        </li>
      </ol>
    </section>

    <div class="mt-4 grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] items-start">
      <div class="space-y-4 min-w-0">
        <div class="sheet p-4">
          <h2 class="sheet-title mb-2">{{ t("orderDetail.lines") }}</h2>
          <ul class="text-sm text-slate-700 space-y-1">
            <li v-for="line in order.lines" :key="line.id">
              <span class="tabular-nums text-slate-500">{{ line.quantity }} ×</span>{{ " " }}<router-link :to="`/knife-models/${line.knife_model_id}`" class="link-action">{{ line.knife_model_name }}</router-link>
            </li>
          </ul>
          <p v-if="order.notes" class="text-sm text-slate-500 mt-3">{{ t("common.notes") }}{{ t("common.colon") }} {{ order.notes }}</p>
        </div>

        <div v-if="feasibility" class="sheet p-4">
          <h2 class="sheet-title mb-2">{{ t("orderDetail.feasibility") }}</h2>
          <div class="-mx-1 overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-slate-500">
                <th class="font-normal pb-1">{{ t("orderDetail.material") }}</th>
                <th class="font-normal pb-1">{{ t("orderDetail.required") }}</th>
                <th class="font-normal pb-1">{{ t("orderDetail.available") }}</th>
                <th class="font-normal pb-1 text-right">{{ t("orderDetail.status") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in feasibility.materials" :key="m.material_id">
                <td class="py-1.5 border-t border-slate-100">{{ m.material_name }}</td>
                <td class="border-t border-slate-100">{{ qty(m.required, m.unit) }}</td>
                <td class="border-t border-slate-100">{{ qty(m.available, m.unit) }}</td>
                <td class="border-t border-slate-100 text-right">
                  <span v-if="m.sufficient" class="tag tag-success">✓ {{ t("orderDetail.ok") }}</span>
                  <span v-else class="tag tag-danger">{{ t("orderDetail.short", { n: qty(m.shortfall, m.unit) }) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
          <p class="mt-3 text-sm font-medium" :class="feasibility.feasible ? 'text-green-700' : 'text-red-700'">
            {{ feasibility.feasible ? t("orderDetail.feasibleYes") : t("orderDetail.feasibleNo") }}
          </p>
        </div>
      </div>
      <div class="space-y-4 min-w-0">
        <section class="sheet p-4">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <h2 class="sheet-title">{{ t("documents.title") }}</h2>
            <div class="flex gap-2">
              <button class="btn btn-outline btn-sm" @click="newDocument('quote')">+ {{ t("documents.newQuote") }}</button>
              <button class="btn btn-primary btn-sm" @click="newDocument('invoice')">+ {{ t("documents.newInvoice") }}</button>
            </div>
          </div>
          <ul v-if="documents.length" class="mt-3 divide-y divide-slate-100 text-sm">
            <li v-for="d in documents" :key="d.id" class="py-2 flex items-center gap-3">
              <router-link :to="`/documents/${d.id}`" class="link-action font-medium">{{ t(`documents.kinds.${d.kind}`) }} {{ d.number ?? t("documents.draft") }}</router-link>
              <span class="tag" :class="DOCUMENT_STATUS_TAG[d.status]">{{ t(`documents.status.${d.kind}.${d.status}`) }}</span>
              <span class="ml-auto tabular-nums">{{ money(Number(d.total_ttc)) }}</span>
            </li>
          </ul>
          <p v-else class="mt-2 text-sm text-slate-600">{{ t("orderDetail.noDocuments") }}</p>
        </section>
      </div>
    </div>

    <p v-if="actionError" class="text-sm text-red-600 mt-4">{{ actionError }}</p>

    <div class="mt-6 flex items-center gap-3">
      <button v-if="order.status === 'draft'" :disabled="loading" class="btn btn-primary" @click="runAction('confirm')">
        {{ t("orderDetail.confirm") }}
      </button>
      <button v-if="order.status === 'confirmed'" :disabled="loading" class="btn btn-primary" @click="runAction('complete')">
        {{ t("orderDetail.complete") }}
      </button>
      <button v-if="['draft', 'confirmed'].includes(order.status)" :disabled="loading" class="btn btn-outline" @click="runAction('cancel')">
        {{ order.status === "confirmed" ? t("orderDetail.cancelRestock") : t("orderDetail.cancel") }}
      </button>
      <button v-if="['draft', 'cancelled'].includes(order.status)" class="link-danger ml-auto" @click="remove">{{ t("orderDetail.delete") }}</button>
    </div>
  </div>
</template>
