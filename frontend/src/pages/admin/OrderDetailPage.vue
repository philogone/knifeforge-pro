<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/composables/useApi";
import { useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";
import type { FeasibilityResult, Order } from "@/types";

const { t } = useI18n();
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

onMounted(load);

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
        actionError.value = detail.message ?? "Insufficient stock";
      } else {
        actionError.value = String(detail);
      }
    } else {
      actionError.value = "Action failed";
    }
  } finally {
    loading.value = false;
  }
}

async function remove() {
  if (!order.value) return;
  if (!confirm(t("common.confirmDelete"))) return;
  await store.deleteOrder(order.value.id);
  router.push("/orders");
}
</script>

<template>
  <div v-if="order" class="max-w-3xl mx-auto px-4 py-8">
    <router-link to="/orders" class="text-sm text-slate-400">&larr; {{ t("common.backToList") }}</router-link>
    <h1 class="text-2xl font-bold text-slate-900 mt-1">{{ order.customer_name }}</h1>
    <p class="text-sm text-slate-500">{{ order.customer_email }}</p>
    <span class="inline-block mt-2 text-xs font-medium rounded px-2 py-1 bg-slate-100 text-slate-700">{{ t(`orders.status.${order.status}`) }}</span>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mt-6">
      <h2 class="font-semibold text-slate-900 mb-2">{{ t("orderDetail.lines") }}</h2>
      <ul class="text-sm text-slate-700 space-y-1">
        <li v-for="line in order.lines" :key="line.id">
          {{ line.quantity }}x
          <router-link :to="`/knife-models/${line.knife_model_id}`" class="text-indigo-600 hover:underline">{{ line.knife_model_name }}</router-link>
        </li>
      </ul>
      <p v-if="order.notes" class="text-sm text-slate-500 mt-3">{{ t("common.notes") }}: {{ order.notes }}</p>
    </div>

    <div v-if="feasibility" class="bg-white rounded-xl border border-slate-200 p-4 mt-4">
      <h2 class="font-semibold text-slate-900 mb-2">{{ t("orderDetail.feasibility") }}</h2>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-400">
            <th class="font-normal pb-1">{{ t("orderDetail.material") }}</th>
            <th class="font-normal pb-1">{{ t("orderDetail.required") }}</th>
            <th class="font-normal pb-1">{{ t("orderDetail.available") }}</th>
            <th class="font-normal pb-1"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in feasibility.materials" :key="m.material_id">
            <td class="py-1">{{ m.material_name }}</td>
            <td>{{ m.required }} {{ m.unit }}</td>
            <td>{{ m.available }} {{ m.unit }}</td>
            <td>
              <span v-if="m.sufficient" class="text-green-600">{{ t("orderDetail.ok") }}</span>
              <span v-else class="text-red-600">{{ t("orderDetail.short", { n: `${m.shortfall} ${m.unit}` }) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="mt-2 text-sm font-medium" :class="feasibility.feasible ? 'text-green-600' : 'text-red-600'">
        {{ feasibility.feasible ? t("orderDetail.feasibleYes") : t("orderDetail.feasibleNo") }}
      </p>
    </div>

    <p v-if="actionError" class="text-sm text-red-600 mt-4">{{ actionError }}</p>

    <div class="mt-6 flex items-center gap-3">
      <button v-if="order.status === 'draft'" :disabled="loading" class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2" @click="runAction('confirm')">
        {{ t("orderDetail.confirm") }}
      </button>
      <button v-if="order.status === 'confirmed'" :disabled="loading" class="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2" @click="runAction('complete')">
        {{ t("orderDetail.complete") }}
      </button>
      <button v-if="['draft', 'confirmed'].includes(order.status)" :disabled="loading" class="bg-white border border-slate-300 text-sm font-medium rounded-lg px-4 py-2" @click="runAction('cancel')">
        {{ order.status === "confirmed" ? t("orderDetail.cancelRestock") : t("orderDetail.cancel") }}
      </button>
      <button v-if="['draft', 'cancelled'].includes(order.status)" class="text-sm text-red-600 ml-auto" @click="remove">{{ t("orderDetail.delete") }}</button>
    </div>
  </div>
</template>
