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
  <div class="page max-w-2xl">
    <header class="page-head"><h1 class="page-title">{{ t("settings.title") }}</h1></header>

    <div class="sheet p-5 mb-6">
      <h2 class="sheet-title">{{ t("settings.language") }}</h2>
      <div class="mt-3 flex gap-2">
        <button
          class="btn btn-sm border"
          :aria-pressed="locale === 'fr'"
          :class="locale === 'fr' ? 'bg-accent-600 text-white border-accent-600' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="setLocale('fr' as Locale)"
        >
          Français
        </button>
        <button
          class="btn btn-sm border"
          :aria-pressed="locale === 'en'"
          :class="locale === 'en' ? 'bg-accent-600 text-white border-accent-600' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="setLocale('en' as Locale)"
        >
          English
        </button>
      </div>
    </div>

    <div class="sheet p-5 mb-6">
      <h2 class="sheet-title">{{ t("settings.shop") }}</h2>
      <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.shop.hint") }}</p>
      <div class="mt-3 flex items-end gap-3 flex-wrap">
        <div>
          <label class="field-label" for="settings-f1">{{ t("settings.shop.hourlyRate") }}</label>
          <input id="settings-f1" v-model.number="shop.hourly_rate" type="number" step="any" min="0" class="w-36 input" />
        </div>
        <div>
          <label class="field-label" for="settings-f2">{{ t("settings.shop.defaultMargin") }}</label>
          <input id="settings-f2" v-model.number="shop.default_margin_percent" type="number" step="any" min="0" max="99" class="w-36 input" />
        </div>
        <button class="btn btn-primary" @click="saveShop">{{ t("common.save") }}</button>
        <span v-if="shopSaved" class="text-sm text-green-700">{{ t("settings.shop.saved") }}</span>
      </div>
    </div>

    <div class="sheet p-5 mb-6">
      <h2 class="sheet-title">{{ t("settings.mockData") }}</h2>
      <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.mockData.hint") }}</p>
      <p class="mt-3 text-sm">
        {{ t("settings.mockData.status") }}{{ t("common.colon") }}
        <span :class="enabled ? 'text-green-700' : 'text-slate-500'">{{ enabled ? t("settings.mockData.enabled") : t("settings.mockData.disabled") }}</span>
      </p>
      <div class="mt-3 flex gap-3">
        <button :disabled="busy" class="btn btn-outline" @click="seed">{{ t("settings.mockData.seed") }}</button>
        <button :disabled="busy" class="btn btn-outline text-red-700 hover:text-red-800 hover:border-red-300" @click="clear">{{ t("settings.mockData.clear") }}</button>
      </div>
    </div>

    <div class="sheet p-5">
      <h2 class="sheet-title">{{ t("settings.backup") }}</h2>
      <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.backup.hint") }}</p>
      <div class="mt-3">
        <button :disabled="exporting" class="btn btn-secondary" @click="exportData">
          {{ t("settings.backup.export") }}
        </button>
      </div>
    </div>
  </div>
</template>
