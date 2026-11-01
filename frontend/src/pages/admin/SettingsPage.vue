<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { type Locale, useI18n } from "@/i18n";
import { useAppStore } from "@/stores/app.store";

const { t, locale, setLocale } = useI18n();
const store = useAppStore();
const enabled = ref(false);
const busy = ref(false);
const exporting = ref(false);

const shop = reactive({ hourly_rate: 0, default_margin_percent: 0 });
const shopSaved = ref(false);
async function refreshShop() {
  const s = await store.fetchShopSettings();
  Object.assign(shop, s);
}
async function saveShop() {
  shopSaved.value = false;
  await store.updateShopSettings(shop);
  shopSaved.value = true;
}

async function refresh() {
  enabled.value = (await store.mockDataStatus()).enabled;
}
onMounted(() => {
  refresh();
  refreshShop();
});

async function seed() {
  busy.value = true;
  try {
    await store.seedMockData();
    await refresh();
  } finally {
    busy.value = false;
  }
}

async function clear() {
  if (!confirm(t("settings.mockData.confirmClear"))) return;
  busy.value = true;
  try {
    await store.clearMockData();
    await refresh();
  } finally {
    busy.value = false;
  }
}

async function exportData() {
  exporting.value = true;
  try {
    const data = await store.exportData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `knifeforge-export-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-6">{{ t("settings.title") }}</h1>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-6">
      <h2 class="font-semibold text-slate-900">{{ t("settings.language") }}</h2>
      <div class="mt-3 flex gap-2">
        <button
          class="text-sm font-medium rounded-lg px-4 py-2 border"
          :class="locale === 'fr' ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-300 text-slate-600'"
          @click="setLocale('fr' as Locale)"
        >
          Français
        </button>
        <button
          class="text-sm font-medium rounded-lg px-4 py-2 border"
          :class="locale === 'en' ? 'bg-indigo-600 text-white border-indigo-600' : 'border-slate-300 text-slate-600'"
          @click="setLocale('en' as Locale)"
        >
          English
        </button>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-6">
      <h2 class="font-semibold text-slate-900">{{ t("settings.shop") }}</h2>
      <p class="text-sm text-slate-500 mt-1">{{ t("settings.shop.hint") }}</p>
      <div class="mt-3 flex items-end gap-3 flex-wrap">
        <div>
          <label class="block text-xs text-slate-500 mb-1">{{ t("settings.shop.hourlyRate") }}</label>
          <input v-model.number="shop.hourly_rate" type="number" step="any" min="0" class="w-36 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-xs text-slate-500 mb-1">{{ t("settings.shop.defaultMargin") }}</label>
          <input v-model.number="shop.default_margin_percent" type="number" step="any" min="0" max="99" class="w-36 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <button class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg px-4 py-2" @click="saveShop">{{ t("common.save") }}</button>
        <span v-if="shopSaved" class="text-sm text-green-600">{{ t("settings.shop.saved") }}</span>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-6">
      <h2 class="font-semibold text-slate-900">{{ t("settings.mockData") }}</h2>
      <p class="text-sm text-slate-500 mt-1">{{ t("settings.mockData.hint") }}</p>
      <p class="mt-3 text-sm">
        {{ t("settings.mockData.status") }}:
        <span :class="enabled ? 'text-green-600' : 'text-slate-500'">{{ enabled ? t("settings.mockData.enabled") : t("settings.mockData.disabled") }}</span>
      </p>
      <div class="mt-3 flex gap-3">
        <button :disabled="busy" class="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2" @click="seed">{{ t("settings.mockData.seed") }}</button>
        <button :disabled="busy" class="bg-red-50 hover:bg-red-100 disabled:opacity-50 text-red-700 text-sm font-medium rounded-lg px-4 py-2" @click="clear">{{ t("settings.mockData.clear") }}</button>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-slate-200 p-4">
      <h2 class="font-semibold text-slate-900">{{ t("settings.backup") }}</h2>
      <p class="text-sm text-slate-500 mt-1">{{ t("settings.backup.hint") }}</p>
      <div class="mt-3">
        <button :disabled="exporting" class="bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2" @click="exportData">
          {{ t("settings.backup.export") }}
        </button>
      </div>
    </div>
  </div>
</template>
