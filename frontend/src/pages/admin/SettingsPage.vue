<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { type Locale, useI18n } from "@/i18n";
import { type ThemeChoice, useTheme } from "@/composables/useTheme";
import { errorMessage } from "@/i18n/apiErrors";
import { useAppStore } from "@/stores/app.store";

const { t, locale, setLocale } = useI18n();
const store = useAppStore();
const theme = useTheme();
const themeChoices: ThemeChoice[] = ["system", "light", "dark"];
const enabled = ref(false);
const busy = ref(false);
const exporting = ref(false);

const shop = reactive({ hourly_rate: 0, default_margin_percent: 0 });

// ---- workshop identity, printed in the client plan's title block
const workshop = reactive({ workshop_name: "", workshop_contact: "", workshop_logo: "" });
const workshopSaved = ref(false);
const workshopError = ref("");
const LOGO_MAX_BYTES = 250_000;

function onLogo(ev: Event) {
  workshopError.value = "";
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (!["image/png", "image/jpeg", "image/svg+xml"].includes(file.type)) {
    workshopError.value = t("settings.workshop.logoType");
    return;
  }
  if (file.size > LOGO_MAX_BYTES) {
    workshopError.value = t("settings.workshop.logoSize");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => (workshop.workshop_logo = String(reader.result));
  reader.readAsDataURL(file);
}

async function saveWorkshop() {
  workshopSaved.value = false;
  workshopError.value = "";
  try {
    await store.updateShopSettings({ ...workshop });
    workshopSaved.value = true;
  } catch (err) {
    workshopError.value = errorMessage(err, t);
  }
}
const shopSaved = ref(false);
async function refreshShop() {
  const s = await store.fetchShopSettings();
  shop.hourly_rate = s.hourly_rate;
  shop.default_margin_percent = s.default_margin_percent;
  workshop.workshop_name = s.workshop_name ?? "";
  workshop.workshop_contact = s.workshop_contact ?? "";
  workshop.workshop_logo = s.workshop_logo ?? "";
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

// ---- restorable backup
const backupBusy = ref(false);
const backupMsg = ref("");
const backupError = ref("");

function saveJson(data: unknown, name: string) {
  const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function downloadBackup() {
  backupBusy.value = true;
  backupError.value = "";
  try {
    saveJson(await store.downloadBackup(), `knifeforge-sauvegarde-${new Date().toISOString().slice(0, 10)}.json`);
  } catch (err) {
    backupError.value = errorMessage(err, t);
  } finally {
    backupBusy.value = false;
  }
}

async function onRestoreFile(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  backupMsg.value = "";
  backupError.value = "";
  let data: unknown;
  try {
    data = JSON.parse(await file.text());
  } catch {
    backupError.value = t("settings.restore.notJson");
    return;
  }
  if (!confirm(t("settings.restore.confirm", { name: file.name }))) return;
  backupBusy.value = true;
  try {
    const res = await store.restoreBackup(data);
    const total = Object.values(res.restored).reduce((a, b) => a + b, 0);
    backupMsg.value = t("settings.restore.done", { n: total });
    await refreshShop();
  } catch (err) {
    backupError.value = errorMessage(err, t);
  } finally {
    backupBusy.value = false;
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
          :class="locale === 'fr' ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="setLocale('fr' as Locale)"
        >
          Français
        </button>
        <button
          class="btn btn-sm border"
          :aria-pressed="locale === 'en'"
          :class="locale === 'en' ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="setLocale('en' as Locale)"
        >
          English
        </button>
      </div>
    </div>

    <section class="sheet p-5 mb-6" aria-labelledby="theme-title">
      <h2 id="theme-title" class="sheet-title">{{ t("theme.title") }}</h2>
      <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("theme.hint") }}</p>
      <div class="mt-3 flex gap-2" role="radiogroup" :aria-labelledby="'theme-title'">
        <button
          v-for="c in themeChoices"
          :key="c"
          role="radio"
          :aria-checked="theme.choice.value === c"
          class="btn btn-sm border"
          :class="theme.choice.value === c ? 'bg-accent-600 text-white border-accent-600' : 'bg-paper border-slate-300 text-slate-700 hover:bg-slate-50'"
          @click="theme.setTheme(c)"
        >
          {{ t(`theme.${c}`) }}
        </button>
      </div>
    </section>

    <section class="sheet p-5 mb-6" aria-labelledby="workshop-title">
      <h2 id="workshop-title" class="sheet-title">{{ t("settings.workshop") }}</h2>
      <p class="sheet-hint text-sm mt-1 max-w-prose">{{ t("settings.workshop.hint") }}</p>
      <div class="mt-4 grid sm:grid-cols-[1fr_auto] gap-5">
        <div class="space-y-3">
          <label class="block">
            <span class="field-label">{{ t("settings.workshop.name") }}</span>
            <input v-model="workshop.workshop_name" maxlength="120" autocomplete="organization" class="input w-full" />
          </label>
          <label class="block">
            <span class="field-label">{{ t("settings.workshop.contact") }}</span>
            <input v-model="workshop.workshop_contact" maxlength="200" :placeholder="t('settings.workshop.contactExample')" class="input w-full" />
          </label>
        </div>
        <div>
          <span class="field-label">{{ t("settings.workshop.logo") }}</span>
          <div class="w-44 h-20 rounded-lg border border-dashed border-slate-300 bg-slate-50 flex items-center justify-center overflow-hidden">
            <img v-if="workshop.workshop_logo" :src="workshop.workshop_logo" :alt="t('settings.workshop.logoAlt')" class="max-w-full max-h-full object-contain" />
            <span v-else class="text-xs text-slate-500 px-2 text-center">{{ t("settings.workshop.noLogo") }}</span>
          </div>
          <div class="mt-2 flex items-center gap-3">
            <label class="link-action cursor-pointer">
              {{ workshop.workshop_logo ? t("settings.workshop.replaceLogo") : t("settings.workshop.addLogo") }}
              <input type="file" accept="image/png,image/jpeg,image/svg+xml" class="sr-only" @change="onLogo" />
            </label>
            <button v-if="workshop.workshop_logo" type="button" class="link-danger" @click="workshop.workshop_logo = ''">{{ t("common.delete") }}</button>
          </div>
        </div>
      </div>
      <div class="mt-4 flex items-center gap-3">
        <button class="btn btn-primary" @click="saveWorkshop">{{ t("common.save") }}</button>
        <span v-if="workshopSaved" class="text-sm text-green-700" role="status">{{ t("settings.shop.saved") }}</span>
        <span v-if="workshopError" class="text-sm text-red-700" role="alert">{{ workshopError }}</span>
      </div>
    </section>

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
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <button :disabled="backupBusy" class="btn btn-primary" @click="downloadBackup">{{ t("settings.backup.download") }}</button>
        <label class="btn btn-outline cursor-pointer" :class="backupBusy ? 'opacity-50 pointer-events-none' : ''">
          {{ t("settings.restore.button") }}
          <input type="file" accept="application/json,.json" class="sr-only" @change="onRestoreFile" />
        </label>
        <button :disabled="exporting" class="link-action" @click="exportData">{{ t("settings.backup.export") }}</button>
      </div>
      <p class="sheet-hint mt-2 max-w-prose">{{ t("settings.restore.hint") }}</p>
      <p v-if="backupMsg" class="mt-2 text-sm text-green-700" role="status">{{ backupMsg }}</p>
      <p v-if="backupError" class="mt-2 text-sm text-red-700" role="alert">{{ backupError }}</p>
    </div>
  </div>
</template>
